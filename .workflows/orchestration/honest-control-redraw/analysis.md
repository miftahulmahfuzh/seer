# Code Analysis: the thirteen mis-shaped control arms D17 refuses

**Type:** Feature Implementation (lab measurement + one hard-gate rule change)
**Date:** 2026-10-19 18:17:12
**Session ID:** 20261019-181712-C4K9
**Plan:** `docs/plans/HONEST_CONTROL_REDRAW_PLAN.md` (8 phases)
**Worktree:** `/home/miftah/.worktrees/seer/honest-control-redraw` — branch `feature/honest-control-redraw`, base `origin/main` @ `465fcfd`

---

## User Input

### Original User Request

> Re-draw the thirteen mis-shaped control arms that D17 refuses, as amendments under the nine existing method ids — M0047, M0201, M0202, M0208, M0215, M0221, M0225, M0227, M0243.
>
> Why this is worth doing and why it costs no method id: `lab control` on the nine (run read-only 2026-10-19, output below) reports thirteen control arms outside D17's [0.50, 2.00] refuse band on trades or turnover. `lab promote` refuses a method holding one, so nine dev-eligible methods are blocked, and every sentence already written about one of those margins was quoted against a handicapped opponent. The remedy is an `Amendment` block on the existing method file, which appends trials under the same `method_id` and costs no new method id and no extra N.
>
> Read first: docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md (leftover item 1 is this job), engine/src/seer_engine/lab/control_shape.py, engine/src/seer_engine/lab/hardgate.py (D17), and `Amendment` in engine/src/seer_engine/lab/method.py.
>
> The measured state, from `lab control M0047 M0201 M0202 M0208 M0215 M0221 M0225 M0227 M0243`:
>
>     method  control               controls        trades x  turnover x  verdict
>     M0047   M0047-PLC1-MV10       M0047-EQ            0.55        0.50  refuse
>     M0047   M0047-PLC1-MV20       M0047-EQ            0.55        0.51  warn
>     M0201   M0201-PLC1-MV10       M0201-Y20-MV10      2.27        2.13  refuse
>     M0201   M0201-PLC2-MV10       M0201-Y20-MV10      2.26        2.12  refuse
>     M0202   M0202-PLC1-HALF       M0202-Y20-HALF      2.25        2.01  refuse
>     M0202   M0202-PLC2-HALF       M0202-Y20-HALF      2.25        1.99  refuse
>     M0202   M0202-PLC1-HALF-FAST  M0202-Y20-HALF      2.25        2.20  refuse
>     M0208   M0208-HASH-N20        M0208-CGO-N20       4.41        5.20  refuse
>     M0215   M0215-HASH            M0215-CTRL          0.34        0.43  refuse
>     M0215   M0215-HASH-CAP4       M0215-CTRL          0.34        0.43  refuse
>     M0221   M0221-R50             M0221-C50           0.21        0.50  refuse
>     M0225   M0225-R50             M0225-C50           0.19        0.42  refuse
>     M0227   M0227-R20             M0227-S20           0.07        0.12  refuse
>     M0243   M0243-NEAR20-R        M0243-NEAR20        3.01        2.98  refuse
>
> They split into two structurally different failures and the plan should treat them as two families, not thirteen one-offs: five controls trade TOO LITTLE (0.07x-0.55x: M0227, M0225, M0221, M0215, M0047) and four trade TOO MUCH (2.25x-5.20x: M0202, M0201, M0243, M0208). A re-draw rule that fixes one family will not fix the other.
>
> The hard part, and what phase 1 must settle before anything is pre-registered: there is probably ONE reusable way to derive a shape-matched control, and getting it wrong in nine parallel sessions is the expensive failure. The established rule in this lab is to derive the control's name count and stickiness from the real book's OWN calendar each rebalance rather than fixing them (see memory seer-placebo-matched-to-a-books-exact-shape and M0241's SPLIT12 placebo, which matched name-for-name every month and split a 3.8 pt lead into 1.9 shape and 1.9 signal). Prove the rule lands inside the [0.80, 1.25] MATCH band — not merely inside the refuse band — on one pilot method before fanning out.
>
> Cautions the plan must carry:
>
> - Adding an `Amendment` block must NOT move any existing candidate's recorded `config_digest`. `prereg.check_source` and `test_every_recorded_configuration_still_digests_to_its_recorded_digest` enforce it. A new control that needs a new params field must be wrapped behind a NEW allocator id local to the method file — never by adding a field to a shared params dataclass, which moves every recorded digest in the lab (memory: seer-shared-params-cannot-gain-a-field).
> - `Method.__post_init__` refuses a candidate id OR a configuration that any other variant of the method already uses, original or amendment. The re-drawn control must differ in configuration from the one it replaces.
> - D17 classifies by the candidate's `rationale` PROSE, never an id suffix, and it classifies dose-response BEFORE placebo — a dose-response arm carries no ratio at all and reads `not-checked`. Phrasing a re-drawn control as dose-response would make the refusal disappear without fixing anything. That is gaming the check, and the plan must forbid it explicitly.
> - Amendment candidates are capped at 1..6 PER AMENDMENT (not per method lifetime), and the commit that adds the block is the pre-registration — `lab run --amend` refuses an uncommitted or dirty file. `why`, `hypothesis` and `expected_failure` are written before any result is seen.
> - M0225 already carries an amendment (seq 1, 2026-10-18); M0030 and M0053 carry the other two. Check `method_amendments` for each of the nine rather than assuming seq 1, and remember `store.latest_source_sha` reads the newest amendment row before `methods.source_sha`.
> - Quote `trial_funding.mwr` (what `lab show` prints as "your money earned") and never `total_return` or `cagr`: these books are funded with the owner's monthly top-up and the curve-shape columns count his deposits as gains.
> - A re-drawn control may well make a method's recorded margin WORSE or reverse it. That is the point and it must be reported as the finding, never tuned away. Re-drawing until a margin survives is exactly what design section 4 forbids.
> - Do not spend a test-window look. Four are spent and all four failed. `lab test` is never invoked and `SEER_RESEARCH_TEST_STORE` is never read.
>
> Environment: `SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite`, `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research`, never rebuild a store. A read-only `sqlite3 "file:...?mode=ro"` query never migrates the database; any `lab` command does, so hash before and restore by path after. `lab stage` targets the main checkout and its commit takes no pathspec. Never judge a `lab` command by a piped exit code.
>
> Scope note for the phase split: nine methods is too many to design nine times. Expect a pilot phase that settles the re-draw rule on the single clearest case and proves it inside the match band, then a fan-out across the rest, then one close-out that reports which of the nine standing verdicts actually survived their honest control.

### User-Provided Context

The `lab control` table above, run read-only on 2026-10-19. Every ratio in it was re-derived
here from `lab/lab.sqlite` by a read-only `sqlite3 "file:…?mode=ro"` query and matches to the
second decimal (see **The measured state, re-derived** below). The database's
`git hash-object` was `3969f1fa5d2066a42ed47716dd05a66050073592` before and after; no `lab`
command was run during this analysis.

### User-Provided Files

- `docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md`
- `engine/src/seer_engine/lab/control_shape.py`
- `engine/src/seer_engine/lab/hardgate.py` (D17)
- `engine/src/seer_engine/lab/method.py` (`Amendment`)

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Settle ONE reusable way to derive a shape-matched control, and prove it lands inside the [0.80, 1.25] MATCH band on a pilot **before** anything else is pre-registered. |
| R2 | Re-draw every mis-shaped control arm as an `Amendment` block under the nine existing method ids — no new method id, no extra N, no moved `config_digest`, no test-window look. |
| R3 | Report which of the nine standing verdicts survive their honest control, in `trial_funding.mwr`, including margins that worsen or reverse. Never tune. |
| R4 | *(derived, not stated — see Decisions)* `lab promote` must actually stop refusing the nine. The user's stated purpose is that the nine are unblocked; the stated remedy alone does not achieve it. |

---

## Detailed Requirements Understanding

**Problem statement.** Fourteen rows of `lab control` over nine methods report a control arm
whose shape does not match the arm it controls — thirteen `refuse` and one `warn`. D17
(`hardgate.mis_shaped_controls` → `check`) turns any `refuse` into a promotion refusal, and all
nine methods are `dev-eligible` with no test trial, so all nine are blocked at exactly the step
that would let them proceed. Separately and independently of promotion, every sentence of the
form "this book beat its blind draw by X points" written about these nine was quoted against an
opponent carrying a different fee bill and a different cadence, so X is not evidence.

**What must change.** For each blocked book, a control arm that is the book's shape with none of
its identity — one whose recorded `trades` and `turnover` sit inside `WARN_BAND` (0.80x–1.25x)
against the arm it controls — recorded as an `Amendment` under the same `method_id`. Then the
margin re-stated against that arm.

**Success criteria.**

1. One re-draw rule, implemented once in a shared helper, lands inside [0.80, 1.25] on both axes
   on both poles of the failure (a control that traded 0.07x and one that traded 3.01x).
2. Fourteen re-drawn arms recorded under nine `method_amendments` rows; `lab control` on the nine
   reports each new arm `ok`.
3. Every pre-existing `config_digest` unchanged: `test_lab_methods.py` green, including
   `test_every_recorded_configuration_still_digests_to_its_recorded_digest`.
4. `lab promote` no longer refuses on D17 for a method that now holds a band-clean control for
   the book in question (R4).
5. One close-out document naming, per method, the margin before and after, in `trial_funding.mwr`.
6. Dev trials only. `lab test` never invoked; `SEER_RESEARCH_TEST_STORE` never read.

**Key considerations.**

- **The direction of every margin move is predictable and must be pre-registered.** A control
  that traded 0.07x under-paid its fees, so an honestly-shaped replacement earns *less* and the
  book's quoted lead **widens**. A control that traded 4.41x over-paid, so the replacement earns
  *more* and the quoted lead **narrows or reverses**. Those are the two falsifiable predictions,
  one per family, and they go in each `Amendment.hypothesis` before any result is seen.
- **Re-drawing until the shape matches is legitimate; re-drawing until the margin survives is
  not.** The first is what D17 asks for and the rule is settled by construction, not by tuning
  (see the rule candidates below). The second is design §4's prohibition. The plan forbids a
  second amendment on the same arm whose only justification is a disliked margin.
- **Assumption.** The nine method files are frozen against their latest recorded sha, and an
  amendment is the only sanctioned way to grow one. All nine are `dev-eligible` with no test
  trial, so `runner.preflight(amend=True)` admits all nine (verified below).

---

## Analysis Scope

### Explicitly mentioned files

- `docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md`
- `engine/src/seer_engine/lab/control_shape.py` (669 lines)
- `engine/src/seer_engine/lab/hardgate.py` (D17 at :523-583; `mis_shaped_controls` at :831-858; the
  refusal clause at :1776-1798)
- `engine/src/seer_engine/lab/method.py` (`Amendment` at :55-114; `Method.__post_init__` at :157+)

### Discovered related files

| File | Why it is in scope |
|---|---|
| `engine/src/seer_engine/lab/runner.py` | `preflight(amend=True)` :261-338, `pending_amendment` :214, `AMEND_CLOSED` :211 |
| `engine/src/seer_engine/lab/prereg.py` | `check_source` :437-477 — the sha equality an amendment temporarily breaks |
| `engine/src/seer_engine/backtest/registry.py` | `_canon` :302-332 — **renders a dataclass by `fields()`, not `as_dict()`** |
| `engine/src/seer_engine/commands/lab.py` | `--amend` :247-256, the run's control print :1751-1798, `_control` :2821-2870 |
| `engine/src/seer_engine/commands/backtest_dev.py` | `registry_problem` :486-515 — checks **one file**, in its own directory |
| `engine/src/seer_engine/lab/store.py` | `latest_source_sha`, `begin_immediate` :896-901, `method_amendments` schema |
| `engine/src/seer_engine/lab/methods/m0187_placebo_hash_order.py` | `draw(seed, symbol, data_date)` :98-101 — the month-keyed hash six of the nine import |
| `engine/src/seer_engine/lab/methods/m0241_stock_split_drift.py` | `placebo_book` :231-266 — the lab's only existing shape-matched placebo, and it still only **warns** |
| the nine method files | the arms to be amended |
| `engine/tests/test_lab_methods.py` | the sha freeze :154-184 and the digest freeze :187-218; `test_allocator_ids_are_unique_across_methods` :108-115; `test_allocator_contract` :88-103 |
| `engine/tests/test_lab_control_shape.py`, `test_lab_hardgate.py`, `test_lab_amendments.py` | the tests the D17 change must extend |

**Not in scope, verified by grep:** nothing under `web/` references `control_shape`,
`controlShape` or `mis_shaped`. D17 has no web surface, so no TS/Python mirror has to move with
it.

---

## Current Dataflow

### Entry point A: `lab control [MNNNN …]`

**Location:** `commands/lab.py:2821` (`_control`)
**Trigger:** CLI subcommand, report-only.
**Reads:** the method's arms from its `lab/methods/mNNNN_*.py` file via `control_shape.survey`,
and the recorded `trials` rows (`window = 'dev'` always, `control_shape.WINDOW`).
**Writes:** nothing. No `trials`, `insights`, `method_folds` or status row moves.
**Exit:** a formatted table on stdout.

### Entry point B: `lab run MNNNN --amend`

**Location:** `commands/lab.py:1686-1811`

1. `amend = bool(getattr(args, "amend", False))` (:1688).
2. `runner.preflight(conn, method, path, amend=amend)` (:1689) →
   - `registry_problem(path)` — git `status --porcelain -- <basename>` and `ls-files
     --error-unmatch` run with `cwd=path.parent`. **Only this one file's state is checked, so
     nine sessions in one shared checkout may each commit their own method file and run.**
   - `real_cost_problem(method)` over `all_candidates()`.
   - method row must exist with a non-null `source_sha`; status must not be in `AMEND_CLOSED`
     (`promoted`, `test-passed`, `test-failed`, `paper`); no `window = 'test'` trial.
   - `pending_amendment(conn, method)` → `method.amendments[k]` where `k` is the number of
     recorded rows; every recorded row is compared field by field, so the record must stay a
     prefix of the file.
   - the "configuration already ran" check is made **only against this amendment's candidates**.
   - **`preflight(amend=True)` does not compare the file's sha to anything.** That is the whole
     mechanism by which a file may grow a block.
3. The amendment's candidates run on the dev window.
4. `runner.record(..., amend=amend)` (:1720) appends one `method_amendments` row carrying the
   file's **new** sha, under `BEGIN IMMEDIATE` (`store.begin_immediate` :896). The lock is taken
   at record time, not for the backtest, so parallel runs serialize only at the write.
5. :1751-1798 prints the run's own control-shape reading and **refuses nothing** (D15).
6. :1799-1811 prints the amendment block; `status` is printed as unchanged — *"an amendment
   appends trials, it never moves"* a status.

### Entry point C: `lab promote MNNNN` → `hardgate.check`

**Location:** `hardgate.py:1776-1798`

```
off_shape = mis_shaped_controls(conn, method_id)
if off_shape:
    raise store.LabError(… "There is no override -- if the rule is wrong, change it in
    seer_engine/lab/hardgate.py and argue for it in the commit")
```

`mis_shaped_controls` (:831-858) → `control_shape.for_method` → `findings` → `refusals`.

### The detection and resolution chain (`control_shape.py`)

1. **`kind_of(arm)`** reads `arm.rationale.lower()` and tests `DOSE_MARKERS` **before**
   `DRAW_MARKERS` before `ABLATION_MARKERS`. The rationale is outside `config_digest`
   (`method.config_text` reads rules, allocator id and params only), so its wording moves no
   recorded digest. Only `KIND_PLACEBO` is shape-checked.
2. **`resolve_target(control, arms)`** — four rungs: `declared` (the `controls` attribute, which
   no candidate carries), `sibling-stem` (the id with its last `-` segment removed, when that
   names a real arm), `declared-idea` (an arm whose rationale opens "The idea:" / "The
   yardstick:"), `first-declared`. **Every rung draws only from `_eligible_targets` — arms that
   are not themselves placebo or dose.**
3. **`findings`** builds one `Finding` per control arm from the recorded `trades` and `turnover`,
   as ratios through `band_verdict`, taking `worst` of the two axes.
4. **`refusals`** keeps the `REFUSE` ones; `hardgate` raises on a non-empty tuple.

### Data persistence

| Table | Written by | Shape |
|---|---|---|
| `trials` | `lab run --amend` | one row per amendment candidate; `UNIQUE(candidate_id, window)`, `UNIQUE(config_digest, window)`; append-only triggers |
| `trial_funding` | `lab run` | `trial_n` PK → `mwr`, `spy_tr_mwr`, `deposits_usd`, … append-only |
| `method_amendments` | `runner.record(amend=True)` | `(method_id, seq)` PK, `source_sha`, `added`, `why`, `hypothesis`, `expected_failure`, `run_at`, `git_sha`; append-only triggers on update **and** delete |
| `methods.source_sha` | `lab run` once | `methods_source_sha_once` trigger refuses any move; later shas live in `method_amendments` |

---

## Key Data Structures

### `Amendment` — `lab/method.py:55`

```python
added: date; why: str; hypothesis: str; expected_failure: str
candidates: tuple[Candidate, ...]      # 1..MAX_VARIANTS (6) PER AMENDMENT
```

`MAX_VARIANTS = 6` (`method.py:40`). The cap is per amendment, not per method lifetime.

### `Method.__post_init__` — `lab/method.py:157`

Walks `[("", self.candidates)] + [(f" amendment {i} …", a.candidates) …]` sharing one `ids` set
and one `digests` set. A candidate repeating **an id** or **a configuration** that any other
batch of this same method already used raises at import. So a re-drawn control must differ from
the arm it replaces in `rules`, `allocator.id` or `params`.

### `config_text` / `config_digest` — `lab/method.py:44-52`

```python
"\n".join((f"rules={_canon(c.rules)}", f"allocator=<{c.allocator.id}>", f"params={_canon(c.params)}"))
```

### `registry._canon` on a dataclass — `backtest/registry.py:323-332`

```python
inner = ",".join(f"{f.name}={_canon(getattr(value, f.name))}"
                 for f in fields(value) if f.compare and not (pinned and is_pinned_default(...)))
```

**This is the single most load-bearing fact in the whole job.** `_canon` enumerates
`dataclasses.fields()`, **not** the hand-written `as_dict()` each params class also carries. So:

- adding *any* `compare=True` field to a params dataclass — even one local to the method file,
  even with a default — moves every recorded `config_digest` that used it;
- adding a `compare=False` field keeps the digests stable but makes the new arm's configuration
  **identical** to the old one's, which `Method.__post_init__` then refuses as *"repeats another
  variant's configuration"*.

The only safe route is therefore the one M0225 already demonstrates: **a new allocator class
local to the method file with a new `id`**, optionally paired with a **new** params dataclass of
its own. `M0225`'s `RepairedCapTopAllocator(CapTopAllocator)` with `id = "M0225"`
(`m0225_…py:62-67`) is the template.

### `Shape` / `Finding` — `control_shape.py`

`Shape(candidate_id, n, trades, turnover)`; `Finding(method_id, control_id, kind, target_id,
rung, control, target, trade_ratio, turnover_ratio, verdict, reason)` with
`refused` (`verdict == REFUSE`) and `flagged` (`WARN` or `REFUSE`).

`WARN_BAND = (0.8, 1.25)`, `REFUSE_BAND = (0.5, 2.0)`, both log-symmetric.

---

## The measured state, re-derived

Every row below comes from one read-only query against `lab/lab.sqlite`
(`trials` joined to `trial_funding`, `window = 'dev'`). `mwr` is `trial_funding.mwr`; SPY TR on
the same deposits is **7.19%/yr** for every one of these trials.

| method | arm | trial | trades | turnover | mwr % | worst fall % |
|---|---|---|---|---|---|---|
| M0047 | `M0047-EQ` | 719 | 1606 | 8.899 | **13.67** | 20.6 |
| M0047 | `M0047-MV10` | 720 | 1600 | 9.345 | 11.15 | 20.0 |
| M0047 | `M0047-MV20` | 721 | 1591 | 9.853 | 10.42 | 24.0 |
| M0047 | `M0047-MV` | 722 | 1585 | 10.073 | 11.12 | 23.6 |
| M0047 | `M0047-PLC1-MV10` | 723 | **881** | **4.415** | 9.87 | 22.9 |
| M0047 | `M0047-PLC1-MV20` | 724 | **876** | **4.522** | 9.88 | 25.8 |
| M0201 | `M0201-Y20-MV10` | 725 | 433 | 2.421 | 9.54 | 55.2 |
| M0201 | `M0201-PLC1-MV10` | 729 | **981** | **5.169** | 10.26 | 53.4 |
| M0201 | `M0201-PLC2-MV10` | 730 | **979** | **5.126** | 8.06 | 58.9 |
| M0202 | `M0202-Y20-HALF` | 662 | 440 | 2.353 | 12.65 | 38.0 |
| M0202 | `M0202-Y20-HALF-FAST` | 663 | 440 | 2.706 | 12.14 | 49.7 |
| M0202 | `M0202-PLC1-HALF` | 665 | **989** | **4.718** | 11.30 | 31.3 |
| M0202 | `M0202-PLC2-HALF` | 666 | **988** | **4.689** | 9.56 | 39.9 |
| M0202 | `M0202-PLC1-HALF-FAST` | 667 | **989** | **5.176** | 11.38 | 39.8 |
| M0208 | `M0208-CGO-N20` | 677 | 624 | 3.061 | **13.88** | 24.9 |
| M0208 | `M0208-HASH-N20` | 680 | **2749** | **15.910** | 8.01 | 23.9 |
| M0215 | `M0215-CTRL` | 707 | 528 | 4.780 | 10.62 | 18.7 |
| M0215 | `M0215-CAP4` | 709 | 500 | 4.562 | 10.34 | 19.1 |
| M0215 | `M0215-HASH` | 711 | **179** | **2.045** | 8.66 | 21.9 |
| M0215 | `M0215-HASH-CAP4` | 712 | **179** | **2.050** | 8.62 | 21.0 |
| M0221 | `M0221-C50` | 713 | 360 | 0.445 | 5.63 | 44.9 |
| M0221 | `M0221-R50` | 718 | **76** | **0.222** | 6.72 | 46.2 |
| M0225 | `M0225-C50` | 742 | 375 | 0.457 | 5.85 | 44.9 |
| M0225 | `M0225-R50` | 747 | **73** | **0.194** | 6.74 | 46.2 |
| M0227 | `M0227-S20` | 748 | 608 | 3.419 | **12.95** | 58.7 |
| M0227 | `M0227-R20` | 752 | **41** | **0.401** | 7.73 | 65.1 |
| M0243 | `M0243-NEAR20` | 782 | 1285 | 6.924 | 10.45 | 50.8 |
| M0243 | `M0243-NEAR20-R` | 785 | **3872** | **20.609** | 4.38 | 50.2 |

Every ratio in the user's table reproduces to the second decimal from these two columns
(e.g. `41 / 608 = 0.0674` → 0.07; `3872 / 1285 = 3.013` → 3.01; `15.910 / 3.061 = 5.198` → 5.20).

### Correction to the count

The table carries **fourteen** rows, not thirteen: thirteen `refuse` plus one `warn`
(`M0047-PLC1-MV20`, 0.55x / 0.51x). The warn arm does not block promotion but is the twin of a
refused arm on the same book and is re-drawn with it; the plan therefore carries fourteen
re-drawn arms across nine amendments. Nothing else about the scope changes.

### Two mis-resolutions the ladder reports honestly, which the re-draw also repairs

Both come from `resolve_target` falling through to `first-declared`, which `Finding.rung` reports
as the guess it is:

- **`M0047-PLC1-MV10` and `-MV20` resolve to `M0047-EQ`** (first-declared) but are *size*-weighted
  placebos whose true targets are `M0047-MV10` and `M0047-MV20`. Numerically it barely matters
  (1606 vs 1600 trades), but the quoted margin does: against `EQ` the lead is **+3.80 pts**,
  against the true target `MV10` it is **+1.28 pts**.
- **`M0202-PLC1-HALF-FAST` resolves to `M0202-Y20-HALF`** because its stem `M0202-PLC1-HALF` is
  itself a placebo and is excluded. Its true target is `M0202-Y20-HALF-FAST`.

Naming each re-drawn arm `<target-id>-PLC` makes `sibling-stem` — the strongest rung — resolve it
to exactly the intended book, and removes the guess for every one of the fourteen.

### The two families, by mechanism and not by number

| family | mechanism | arms |
|---|---|---|
| **A — too little** | the hash carries **no date term** (`draw(seed, symbol)`) or is re-keyed on a *quarter*, so the control's book changes only when the pool does | `M0227-R20` (`m0227:117` `draw(seed, symbol)`), `M0221-R50` / `M0225-R50` (`m0221:139` `draw(seed, symbol)`), `M0215-HASH` / `-CAP4` (`m0215:115` quarter-keyed, held-first), `M0047-PLC1-MV10` / `-MV20` (`m0047.placebo_order` only: quarterly re-draw + 40% keep band — the arms they control re-pick fresh every month, see the correction above) |
| **B — too much** | the hash is re-keyed on the **month** (`draw(seed, symbol, data_date)`, M0187's), so the whole book is re-drawn at every decision while the real book's ranking persists | `M0243-NEAR20-R` (`m0243:220`), `M0208-HASH-N20` (`m0208:235`), `M0201-PLC1/2-MV10` (`m0201:166`), `M0202-PLC1/2-HALF`, `-HALF-FAST` (`m0202:159`) |

The two families are the same error with the sign flipped: **the draw's re-key period was chosen
by hand instead of being derived from the book it controls.** `M0243`'s own file says so in
prose (`m0243:50-52`): *"M0227's own placebo used a sticky hash order and traded 41 times in
twenty years, failing the trade-count condition; this one is redrawn each month"* — the author
saw family A, corrected by hand, and overshot into family B. That one sentence is the argument
for a derived rule rather than a hand-chosen period.

### The lab's only existing shape-matched placebo still only warns

`M0241`'s `placebo_book` (`m0241:231-266`) is the state of the art: for each trailing calendar
month, newest first, it counts how many eligible members really split that month and draws that
many names in a hash order seeded on **that month**, stopping at exactly the real book's size.
Its docstring claims *"the monthly draws are stable between rebalances, so the turnover matches
too"*. Measured, it lands at **1.372x trades / 1.131x turnover** — outside the match band. A rule
that merely imitates M0241 will not clear R1's bar.

---

## The re-draw rule: the design space phase 1 must close

A shape-matched control must reproduce the real book's **name-level persistence**, not just its
size. Three constructions are available, and the difference between them is where the
persistence comes from.

**Rule A — churn-matched draw (recommended).** At each decision session the control allocator
recomputes *the real arm's own selection* from the same prepared data at this date and at the
previous decision date, takes `e = |target_now \ target_prev|`, keeps `n - e` of its own `held`
names in a date-free hash order, and draws `e` fresh names from the same eligible pool in a hash
order seeded on the current month. Book size is the real arm's own size that day.

- *Why it should land:* the entry count per rebalance is matched by construction, so the trade
  ratio is ~1.00 analytically rather than empirically. Turnover follows because the weighting
  scheme is the real arm's.
- *Needs:* `held` (supplied to `targets`/`targets_prepared` — and `m0047:189` `placebo_order` and
  `m0215:169` already use it, so a held-reading placebo is an established pattern here); one
  extra recomputation of the target's selection at the previous decision session; the previous
  decision session derived from the calendar, as `M0260` derived its gate anchor.
- *Risks:* lookback must stay ≤ 473 (the smoke fixture's size — memory
  `seer-lab-method-lookback-capped-by-smoke-fixture`); and "previous decision session" means
  different things on two different chassis, which the reconciliation of 2026-10-19 settled:

  > **Correction, 2026-10-19 (reconciliation).** An earlier draft of this bullet called M0047,
  > M0201 and M0202 "the quarterly chassis" together. That is wrong about M0047 and misleading
  > about the other two.
  >
  > **M0047's residual arms are plain MONTHLY re-picks.** `REPICK_MONTHS` and `KEEP_PCT` appear
  > in `m0047_market_value_residual.py` only inside `placebo_order` (`:189-202`); the residual
  > arms recompute the ranking and take a fresh `one_per_company(order, 20)` at every monthly
  > decision (`:244-248`), with no keep band and no quarterly gate. The quarterly band is the
  > **handicap being removed**, not a property to reproduce. M0047's control therefore matches
  > the monthly churn and calls the shared `control_draw.previous_decision_date`.
  >
  > **M0201's and M0202's shared chassis really is quarterly, and the keep band really does
  > govern its churn.** `SizedYieldBetaAllocator._run` and `HalfGuardAllocator._run` both set
  > `repick = not stocks or data_date.month in REPICK_MONTHS` and pass an empty `frac`
  > otherwise, so the allocator is *called* monthly but the basket only *moves* quarterly,
  > behind M0197's 40% keep band. There is no monthly entry count there to match. Those two
  > files derive their own previous re-pick (`prev_repick_session`) and the entry count from the
  > band rather than from a set difference, and the walk measured **0.9549** of the real book's
  > entries over the dev window's 79 re-picks doing it that way.
  >
  > So the shared helper answers the previous **monthly** decision and the quarterly chassis
  > derives its own, and neither half may be generalised to the other. Phase 1's
  > `previous_decision_date` docstring carries the split; phase 4 and phase 5 carry their halves.

**Rule B — cohort-mirrored draw (M0241's, generalised).** Reconstruct the real arm's entry
cohorts and draw per cohort, seeded on the cohort's month. Stateless, no `held`. Measured
precedent: 1.372x / 1.131x — a warn. **Evidence against.**

**Rule C — persistence-inherited permutation.** A fixed symbol→symbol map σ over the store's
universe; the placebo's score for X is the real score of σ(X). Inherits a real name's score
process exactly, so persistence, entry and exit behaviour come for free; stateless and cheap.
*Risk:* the pool thins wherever σ(X) is unscorable that day, and the match is statistical rather
than by construction. A date-free permutation **within the day's pool by rank position** collapses
back to the sticky draw and must not be confused with this.

Phase 1 picks one, proves it on both poles, and the rest of the plan consumes it as a settled
helper. The recommendation is **A**, with **C** as the named fallback if A's previous-decision
derivation proves unsound on the quarterly chassis.

### Three things the rule may not do

1. **It may not be phrased as a dose-response arm.** `kind_of` tests `DOSE_MARKERS` first, and a
   dose arm carries verdict `not-checked` and no ratio at all. Writing "dose-response", "dose:",
   "and not since", "and none since", "does the date do any work" or "on the date itself" into a
   re-drawn control's rationale makes the refusal vanish without fixing anything. Every re-drawn
   arm's rationale must carry a `DRAW_MARKERS` phrase (`"placebo"`, `"hash-drawn"` or
   `"hash order"`) and none of `DOSE_MARKERS`.
2. **It may not touch an existing params dataclass.** See `_canon` above.
3. **It may not be re-drawn a second time because the margin came out wrong.** A second amendment
   on the same book is admissible only when the *shape* missed the band, and the plan requires
   the miss to be stated in the close-out either way.

---

## Dependencies

### Environment

| | |
|---|---|
| `SEER_LAB_DB` | `/home/miftah/seer/lab/lab.sqlite` (the main checkout's file, shared by every session) |
| `SEER_RESEARCH_STORE` | `/home/miftah/seer/engine/.research` — the main checkout's store; **worktrees have none** (memory `seer-research-store-not-in-worktrees`) |
| python | `/home/miftah/seer/engine/.venv/bin/python` with `PYTHONPATH=<worktree>/engine/src` (memory `seer-worktree-tests-need-pythonpath`) |
| never | `lab test`, `SEER_RESEARCH_TEST_STORE`, any store rebuild |

### Verified preconditions

```
id     status        dev_trials  test_trials      method_amendments
M0047  dev-eligible  6           0                (none)
M0201  dev-eligible  6           0                (none)
M0202  dev-eligible  6           0                (none)
M0208  dev-eligible  4           0                (none)
M0215  dev-eligible  6           0                (none)
M0221  dev-eligible  6           0                (none)
M0225  dev-eligible  7           0                seq 1, 2026-10-18 (E100)
M0227  dev-eligible  5           0                (none)
M0243  dev-eligible  5           0                (none)
```

All nine clear `AMEND_CLOSED` and the no-test-trial check. **M0225's block is seq 2**; the other
eight are seq 1. (`M0030` and `M0053` carry the lab's other two amendments and are not in scope.)

### Concurrency facts that shape the DAG

- `registry_problem` checks **one file**, so nine sessions in one checkout can each commit their
  own method file and run (`backtest_dev.py:486-515`).
- The lab's write lock is `BEGIN IMMEDIATE`, taken at record time only (`store.py:896`), so
  parallel `lab run --amend` sessions serialise at the write and not across the backtest.
- `test_lab_methods.py` reads the **committed** lab database (`_committed_lab()`), and its sha
  check falls back to `runner.pending_amendment`, so a committed-but-unrun `Amendment` block
  keeps the suite green throughout the batch.
- `lab stage` regenerates `web/data/lab.json` from the whole database and git-adds it with
  `lab.sqlite`, targeting the **main checkout** (memory `seer-lab-stage-targets-the-main-checkout`),
  and the snapshot test reads the working tree, so it is red mid-batch (memory
  `seer-lab-stage-commit-needs-the-index`). **Only the close-out phase may run it.**

---

## Reference List

| Symbol / key | File:line | Kind | Owner phase |
|---|---|---|---|
| `mis_shaped_controls` | `lab/hardgate.py:831` | def | 2 |
| D17 prose | `lab/hardgate.py:523-583` | doc | 2 |
| the D17 refusal clause | `lab/hardgate.py:1776-1798` | call | 2 |
| `control_shape.refusals` | `lab/control_shape.py` | def | 2 |
| `control_shape.findings` | `lab/control_shape.py:466` | def | 2 |
| `control_shape.format_report` | `lab/control_shape.py` | def | 2 |
| `_control` | `commands/lab.py:2821-2870` | call | 2 |
| the run's control print | `commands/lab.py:1751-1798` | call | 2 |
| `test_lab_control_shape.py` | `engine/tests/` | test | 2 |
| `test_lab_hardgate.py` | `engine/tests/` | test | 2 |
| the matched-draw helper | *new* `lab/control_draw.py` | def | 1 |
| `M0227.IssuanceParams`, `draw`, `IssuanceAllocator` | `lab/methods/m0227_net_share_shrinkers.py:76-230` | impl | 1 |
| `M0243.NearShrinkParams`, `draw` use | `lab/methods/m0243_shrinkers_near_high.py:107-254` | impl | 1 |
| `M0221.CapTopParams`, `draw`, `CapTopAllocator` | `lab/methods/m0221_cap_weighted_top_n.py:88-230` | impl | 3 |
| `M0225.RepairedCapTopAllocator` | `lab/methods/m0225_cap_weighted_top_n_repaired.py:62-67` | impl | 3 |
| `M0047.SizeParams`, `placebo_order` | `lab/methods/m0047_market_value_residual.py:110-250` | impl | 4 |
| `M0201.SizedYieldBetaParams`, `scored` | `lab/methods/m0201_treasury_beta_size_weighted.py:95-240` | impl | 5 |
| `M0202.HalfGuardParams`, `scored` | `lab/methods/m0202_treasury_beta_half_guard.py:81-240` | impl | 5 |
| `M0208.OverhangParams`, `draw` | `lab/methods/m0208_capital_gains_overhang.py:91-250` | impl | 6 |
| `M0215.CapParams`, `draw`, `choose` | `lab/methods/m0215_sector_capped_calm_raisers.py:65-190` | impl | 7 |
| `m0187.draw(seed, symbol, data_date)` | `lab/methods/m0187_placebo_hash_order.py:98` | impl | 1 (read) |
| `m0241.placebo_book` | `lab/methods/m0241_stock_split_drift.py:231` | impl | 1 (read) |
| `Amendment` | `lab/method.py:55` | def | 1,3,4,5,6,7 |
| `_canon` dataclass branch | `backtest/registry.py:323` | def | 1 (read) |
| `test_every_recorded_configuration_still_digests_to_its_recorded_digest` | `engine/tests/test_lab_methods.py:187` | test | all |
| `test_allocator_ids_are_unique_across_methods` | `engine/tests/test_lab_methods.py:108` | test | all |
| `test_allocator_contract` (P4 identity, no-lookahead) | `engine/tests/test_lab_methods.py:88` | test | all |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/lab/control_draw.py` — **new**: the matched-draw helper, the one place
   the rule lives. *Phase 1.*
2. `engine/src/seer_engine/lab/methods/m0227_net_share_shrinkers.py` — amendment seq 1, one arm
   (`M0227-S20-PLC`). *Phase 1.*
3. `engine/src/seer_engine/lab/methods/m0243_shrinkers_near_high.py` — amendment seq 1, one arm
   (`M0243-NEAR20-PLC`). *Phase 1.*
4. `engine/tests/test_lab_control_draw.py` — **new**: the helper's churn-matching asserted session
   by session on the smoke fixture, before any backtest. *Phase 1.*
5. `engine/src/seer_engine/lab/control_shape.py` — supersession: a refused arm is excused when a
   band-clean sibling placebo resolves to the same target; the refused arm is still reported.
   *Phase 2.*
6. `engine/src/seer_engine/lab/hardgate.py` — D17 prose and `mis_shaped_controls`. *Phase 2.*
7. `engine/src/seer_engine/commands/lab.py` — `lab control` prints "superseded by …"; the run's
   control print and the `lab control` help text follow. *Phase 2.*
8. `engine/tests/test_lab_control_shape.py`, `engine/tests/test_lab_hardgate.py` — the supersession
   rule, and the proof that it changes no verdict on today's lab. *Phase 2.*
9. `engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py` — amendment seq 1, one arm.
   *Phase 3.*
10. `engine/src/seer_engine/lab/methods/m0225_cap_weighted_top_n_repaired.py` — amendment **seq 2**,
    one arm. *Phase 3.*
11. `engine/src/seer_engine/lab/methods/m0047_market_value_residual.py` — amendment seq 1, two arms.
    *Phase 4.*
12. `engine/src/seer_engine/lab/methods/m0201_treasury_beta_size_weighted.py` — amendment seq 1, two
    arms. *Phase 5.*
13. `engine/src/seer_engine/lab/methods/m0202_treasury_beta_half_guard.py` — amendment seq 1, three
    arms. *Phase 5.*
14. `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py` — amendment seq 1, one arm.
    *Phase 6.*
15. `engine/src/seer_engine/lab/methods/m0215_sector_capped_calm_raisers.py` — amendment seq 1, two
    arms. *Phase 7.*
16. `docs/plans/HANDOVER_20261019-the-honest-control.md` — **new**, the close-out. *Phase 8.*
17. `lab/lab.sqlite` + `web/data/lab.json` — staged once, by `lab stage`, in the close-out only.
    *Phase 8.*

**This document describes. The plan files prescribe.**

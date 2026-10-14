# Code Analysis: the roster's width, and the four open method ideas

**Type:** Feature Implementation (one roster change) + Feature Implementation (four lab methods)
**Date:** 2026-10-14 15:07:38 WIB
**Session ID:** 20261014-150738-B7K4
**Plan:** `docs/plans/ROSTER_35_FOUR_METHODS_PLAN.md` (5 phases)
**Worktree:** none — planned against `main` @ `661870d`, in the main checkout `/home/miftah/seer`.
See "Why no worktree" below; it is a finding of this analysis, not a default.

---

## User Input

### Original User Request

The `/analyze` invocation:

> `docs/plans/HANDOVER_20261014-the-bar-the-screen-and-the-width.md` — pick up where 2026-10-14
> left off. Read the handover first; it carries the state, the findings not to re-derive, the
> decisions not to silently reverse, and the traps. The owner's live decision (hold 35 names
> rather than 20) is his to accept or decline and is NOT yours to implement. The research work
> worth planning is M0155 (a single-name brake, which attacks the one hole both existing defences
> leave open), M0156 (survivorship-check M0002-REL-85, the roster book that has never been checked
> at all), M0149 (the asymmetry book braked by its own falling account rather than the market's
> trend) and M0148 (a time-lock on the switch). Test-window looks are 4 and must stay 4.

Then, mid-analysis, the owner sent:

> let's change our seer roster to hold 35 stocks instead of 20

**That second message is the owner accepting the width decision the first message reserved to
him.** The first message's "NOT yours to implement" was a guard against the planner deciding a
real-money question on its own; the owner has now decided it. The guard is satisfied, not
violated, by implementing it. The width change is therefore in scope, and it is R1.

### User-Provided Context

`docs/plans/HANDOVER_20261014-the-bar-the-screen-and-the-width.md` — read in full. Its load-bearing
content for this plan:

- The lab stands at 473 trials, 170 methods, **test-window looks 4**.
- The width recommendation: 35 names, from M0152, measured on both price histories.
- Four findings not to re-derive (the turnover audit key, the dev store's blindness to width,
  the learned ranker being finished, the switch's two halves wanting opposite things).
- Three decisions not to silently reverse (the width grids stay out of `grid.csv`; M0146 spent no
  method id on purpose; design §18 is not amended).
- Five traps (`lab stage` from a worktree stages main; a rebase replays a stale `lab.sqlite`;
  backticks in a double-quoted `-m`; re-subscribing to an idle session; a background `lab run`
  shell is not a stall).

### User-Provided Files

None marked with `@`. Everything below was discovered by exploration from the handover.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Change the Seer roster to hold 35 stocks instead of 20 |
| R2 | M0155 — a single-name brake: trim a holding falling apart while the market is fine |
| R3 | M0156 — survivorship-check M0002-REL-85, the roster book never checked at all |
| R4 | M0149 — the asymmetry book braked by its own falling account, not the market's trend |
| R5 | M0148 — a time-lock on the safety switch |
| R6 | Do not spend a test-window look: the count is 4 and must stay 4 |

R6 is a constraint on every other R rather than a deliverable of its own. It is carried as a plan
invariant and is restated in each phase's exit criteria.

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** Two unrelated bodies of work land in one session.

The first is a **real-money roster change**. The owner mirrors the paper roster with his own money
(`owner-mirrors-the-paper-roster-with-real-money`), so moving a paper book from 20 names to 35
moves what he buys. The evidence is M0152's width curve, read on the survivorship-check store:
at 20 names the roster's residual-momentum book falls 25.05%, outside the owner's own 25% bar; at
35 names it falls 20.11% and earns slightly *more* (12.11% a year against 11.98%). The mechanism
is dated rather than inferred — spring 2006, a single holding collapsing while SPY dipped 2% and
recovered by September — and it is the only width-sensitive episode in twenty years.

The second is **four pre-registered lab method runs**, each of which closes a question the
2026-10-14 session opened. All four already exist as `idea`-status rows in `lab/lab.sqlite` with
their hypotheses written out at length; those rows are the specification and this analysis does not
re-invent them.

**Success Criteria.**

- R1: a new roster entry holding 35 names trades on the next nightly, `RAW-FR-GT` is retired, no
  started entry's spec digest moves, and the whole engine + web test suite is green.
- R2–R5: each method file is committed *before* its `lab run` (the commit is the pre-registration),
  the run records its trials, a verdict is written, and `lab stage` keeps `lab.sqlite` and
  `web/data/lab.json` agreeing row for row.
- R6: `store.test_looks` reads 4 before and after every phase.

**Key Considerations.**

1. **A changed strategy is a new id, never an edited entry.** `paper/roster.py`'s module docstring
   and `docs/runbooks/paper-trading.md` §"Frozen means frozen" both state it, and
   `paper/store.py:285 check_digest` enforces it: a started entry whose stored spec digest differs
   from the code's fails the whole paper night with `SpecMismatch`, rolled back. So R1 cannot be a
   one-line edit to `RESIDMOM_PARAMS`; that would re-digest a running entry and stop the board.
2. **A roster entry's params must name a recorded lab trial.** `LAB_PROVENANCE` carries the method
   and variant, and `tests/test_paper_roster.py` checks the variant is one of that method's
   recorded trials in the committed `lab/lab.sqlite`. So R1 needs a 35-name variant that has
   already run. One exists — see "The 35-name book already has a recorded trial" below.
3. **The method ids are already reserved.** M0148, M0149, M0155 and M0156 are `idea` rows in
   `methods`; `store.next_method_id` returns `M0157`. No id is minted by this plan; four are spent.
4. **Each method that records a dev trial moves N.** The luck gate's N counts methods
   (`seer-lab-n-policy-overcounts-looks`), and the move is applied retroactively to every recorded
   verdict. Four runs is N + 4 on every published verdict in the lab. That is a known, accepted
   cost of asking four questions; it is stated here so no phase is surprised by a verdict that
   moved without its doing.
5. **The test window is never read.** `lab survivorship`, `lab kin`, `lab exposure` and `lab gate`
   all record no trial and cannot move `test_looks`; `lab run` names the dev window. Nothing in
   this plan calls `lab test`.

---

## Analysis Scope

### Explicitly Mentioned Files

- `docs/plans/HANDOVER_20261014-the-bar-the-screen-and-the-width.md` (the handover)

### Discovered Related Files

| File | How it was reached |
|---|---|
| `lab/lab.sqlite` | the handover's state; queried read-only through a scratchpad copy |
| `engine/src/seer_engine/lab/method.py` | `Method` / `Amendment` / `config_digest`, the method contract |
| `engine/src/seer_engine/lab/methods/m0133_gated_updown_asymmetry.py` | M0149's parent |
| `engine/src/seer_engine/lab/methods/m0113_trend_switch_reentry.py` | M0148's switch and `entry_on` |
| `engine/src/seer_engine/lab/methods/m0109_book_drawdown_brake.py` | M0149's and M0155's brake prior art |
| `engine/src/seer_engine/lab/methods/m0152_roster_width_rungs.py` | the width curve's candidates |
| `engine/src/seer_engine/lab/methods/m0139_names_on_an_invested_tape.py` | **holds the 35-name variant** |
| `engine/src/seer_engine/lab/survivorship_check.py` | R3 step one's machinery |
| `engine/src/seer_engine/lab/survivorship_record.py` | `GRID_PATH`, why the grids stay unmerged |
| `engine/src/seer_engine/commands/lab.py` | every `lab` subcommand's arguments |
| `engine/src/seer_engine/commands/promote.py` | the lab→roster bridge R1 must travel |
| `engine/src/seer_engine/paper/roster.py` | `RESOLVER`, `LAB_PROVENANCE`, `SEED_ROWS`, `spec_digest` |
| `engine/src/seer_engine/paper/store.py:285` | `check_digest` — why a change is a new id |
| `engine/src/seer_engine/strategies/evidence.py:682–691` | `EVIDENCE`, keyed by `object_name` |
| `engine/src/seer_engine/sim/rules.py:282` | `MONTHLY_HOLD_FRAC_GOTRADE_TBAND` |
| `db/migrations/017_roster_real_fees.sql` | the pattern a roster-change migration follows |
| `db/migrations/013_roster_first_night.sql` | the prose style a roster decision is argued in |
| `docs/runbooks/paper-trading.md:53–86` | the roster-change checklist, verbatim |
| `docs/lab/survivorship/roster-width-curve-2026-10-14.csv` | the measured curve |
| `engine/tests/test_paper_roster.py` | `PINS`, the digest pins R1 must extend |
| `.claude/skills/calculate-assets/build_audit.py:14–16` | hardcodes roster id → lab variant |

---

## Current Dataflow

### Entry Point A: `lab run MNNNN` — a pre-registered method reaches the dev window

**Location:** `engine/src/seer_engine/commands/lab.py:205` (parser), `:1546` (`_run`)
**Trigger:** the operator, after committing the method file
**Input:** a method id; `--store` (default `$SEER_RESEARCH_STORE` or `research.STORE_DIR`);
`--allow-coverage`; `--amend`

**Validation, before any bar is read.** `lab/prereg.py` refuses an uncommitted or dirty method
file and a `config_digest` the `trials` table already holds. The commit *is* the pre-registration;
this is the lab's whole integrity story and the reason the method file is written and pushed
before the run, never after.

**Transform.** `discover()` imports every `mNNNN_*.py`, validates `METHOD` through
`Method.__post_init__` (1–6 candidates, ids prefixed `MNNNN-`, no repeated id or configuration),
and `dev.run_registry` backtests each candidate over the dev window (opens 1996-01-03, closes
**2015-10-16**) at the recorded capital and the owner's contribution schedule.

**Exit.** One `trials` row per candidate (append-only; `trials_no_update` and `trials_no_delete`
triggers), plus `trial_moments`, `trial_funding` and `trial_provenance`. `methods.source_sha` is
written exactly once. Exit 0 ok, 2 refused by a lab rule, 1 error.

**State changes.** `lab/lab.sqlite` grows. The lab's N — the luck gate's multiple-testing count —
moves by one **method**, not by the number of candidates.

### Entry Point B: `lab survivorship MNNNN` — the same trials on the honest price history

**Location:** `engine/src/seer_engine/lab/survivorship_check.py`, parser at `commands/lab.py:~477`
**Trigger:** the operator; R3 step one is exactly this call on `M0002`

**Transform.** Every variant of the named method that has a recorded dev trial *and* is still in
the method file is re-run twice at that trial's recorded capital and funding: once on
`engine/.research` (the dev store, ~59% of index-member days, overwhelmingly survivors) and once
on `engine/.research-sv` (manifest `purpose: "survivorship-check"`, the EODHD store that adds the
bankrupted, bought and renamed companies back). The two are printed side by side.

**Exit / state.** Nothing but one `observation` journal row per method unless `--no-journal`. No
`trials`, no `trial_moments`, no `trial_funding`, no `trial_provenance`, no status move. So
`store.dev_trial_count` and `store.test_looks` **cannot** move — which is why R3 step one is free
and why it is the first thing the plan does.

**Memory.** Each store is ~2.5M bar rows; `measure_store` loads one, runs every variant, keeps
only small `Side` records and drops the store before the other is loaded. The two are never alive
together. (`seer-research-store-memory-budget`: ~1.79 MB/symbol loaded whole.)

### Entry Point C: `promote` — a lab variant becomes a paper roster entry

**Location:** `engine/src/seer_engine/commands/promote.py`
**Trigger:** the operator; R1 travels this path

**Validation — three things, and it refuses anything that is not all three:**

1. the method file exposes the variant as a `Candidate` (a frozen rules/allocator/params triple);
2. the allocator is a value `paper.roster.RESOLVER` names — *and the resolver binds the params
   too*, so a different `params` needs a **different resolver key**;
3. that key has an entry in `strategies.evidence.EVIDENCE` — a strategy that cannot say why it
   picked a stock does not go on the site.

**Transform / Exit.** One `strategies` row: display columns, `object_name`, `registry_id` NULL,
`gate_note`, `gate_applicable`, `status='active'`, `promoted_from`, the frozen `params` (spec,
digest, backtest_gate), and **no** `paper_start`. The row is read back through `roster.from_row`
inside the same transaction before it commits. `--retire <id>` flips the outgoing row to
`'retired'` in that same transaction, so the board never shows the wrong count.

**Two databases, one promotion.** The roster is Neon, the lab is `lab/lab.sqlite`; no shared
transaction. Lab rules are checked first and write nothing, the roster transaction commits, then
the lab note commits. The only partial outcome is "roster written, lab note missing", and
re-running the identical command repairs it.

### Entry Point D: the nightly paper step — where a roster change actually takes effect

**Location:** `.github/workflows/nightly.yml` → `commands/paper.py` → `paper/book.py`
**Trigger:** cron `17 6 * * 2-6` (13:17 WIB), retries 16:41 and 19:41 WIB

For every active entry, `paper/store.py:285 check_digest` compares the stored spec digest against
the one `paper/roster.py` recomputes today. A mismatch is `store.SpecMismatch`: the whole night is
rolled back, `runs.paper_status = failed`, exit 1. A **new** entry has no stored digest, so its
first night writes its spec and its `paper_start` — a fresh clock, starting at
`paper/capital.py:11 PAPER_INITIAL_IDR` (10,000,000 IDR) with 5,000,000 IDR arriving on the 25th
of each month (`roster.OWNER_FUNDING`).

### Data Persistence

| Store | What | Written by |
|---|---|---|
| `lab/lab.sqlite` | methods, trials, moments, funding, provenance, amendments, insights, ideas | `lab run`, `lab note`, `lab insight`, `lab idea` |
| `web/data/lab.json` | the committed snapshot `/sera` reads | `lab stage` (git-adds it with `lab.sqlite`) |
| Neon Postgres `strategies` | the live roster rows | `db/migrations/*.sql`, `promote` |
| Neon `paper_state`, `paper_positions`, … | each entry's paper clock and book | the nightly paper step |
| `docs/lab/survivorship/*.csv` | the survivorship grids and the width curves | `lab survivorship --csv` |

---

## Key Data Structures

### `Method` — `engine/src/seer_engine/lab/method.py:118`

**Fields:** `id`, `name`, `family`, `source_kind` (one of paper/blog/github/knowledge/variation),
`source_ref`, `hypothesis`, `expected_failure`, `candidates` (1–6 `Candidate`), `parent_id`,
`seen_keys`, `amendments`.

**Used in:** `discover()` (`method.py:200`), `prereg.check_source`, `runner`, `survivorship_check`,
`paper/roster.py` (which imports method modules to read their frozen params).

`config_text(c)` is `rules` + `allocator.id` + `params` — **never the candidate id or family**. The
same configuration under a new id is still a re-run and the lab refuses it. This is why
`seer-shared-params-cannot-gain-a-field` matters: adding a field to a shared params dataclass moves
every recorded config digest in the lab.

### `Amendment` — `method.py:62`

More pre-registered variants of a method that has already run, recorded under the same
`method_id`, so **the lab's N does not move and no method id is spent**. The commit that adds the
block is its pre-registration; `lab run --amend` refuses an uncommitted or dirty file. Relevant to
R3: M0156's step two is a second batch of the same idea and could be an amendment rather than a
fifth method id.

### `RosterEntry` / `RosterRow` — `paper/roster.py:275`

**Fields:** `id`, `name`, `sub`, `icon`, `is_champion`, `is_benchmark`, `sort`, `engine`
(bracket/book/benchmark), `rules`, `obj`, `object_name`, `params`, `registry_id`, `lookback`,
`gate_note`, `gate_applicable`, `status`, `paper_end`, `lab_provenance`.

**The frozen spec** (`spec()`, `spec_text()`, `spec_digest()`) covers engine, object name and id,
registry id and digest, every `TradeRules` field, every param, and the starting capital.
**Deliberately NOT in the spec:** `status`, `paper_end`, `gate_note`, `gate_applicable`,
`lab_provenance` — so retiring an entry, correcting a note or recording why it was admitted never
moves a live digest.

### `RESOLVER` — `paper/roster.py:466`

```python
RESOLVER: dict[str, Binding] = {
    ...
    "RESIDMOM": Binding(obj=RESIDMOM, params=RESIDMOM_PARAMS),   # M0007-N20-RAW
    "REGIME":   Binding(obj=REGIME,   params=REGIME_PARAMS),     # M0002-REL-85
    ...
}
```

**Keys are stable forever** — a stored spec names one, so renaming a key moves a live digest.
Append only. **A new width is a new key**, because the binding carries the params as well as the
object.

### `EVIDENCE` — `strategies/evidence.py:682`

`dict[str, Callable]` keyed by the same `object_name`. `residmom_evidence` (`:411`) takes
`params: Any` and types it as `ResidParams`, so **it works unchanged at any `top`** — a new
resolver key can map to the same function.

---

## The 35-name book already has a recorded trial

This is the finding that makes R1 a plan rather than a research project, and it is worth stating
precisely because the obvious guess is wrong.

M0152 — the method the handover's recommendation comes from — recorded exactly **three** dev
trials: `N25`, `N30`, `N45`. **It has no 35-name variant.** The 35-name rung of the published curve
comes from a different method:

```
names  candidate_id      store  max_dd_daily  funded_yearly  mar     trades
20     M0128-RAW20       dev    0.206495      0.136842       0.6627  1607
20     M0128-RAW20       check  0.250494      0.119781       0.4782  1640     <- outside the 25% bar
35     M0139-N35-TBAND   dev    0.196018      0.130546       0.6660  2548
35     M0139-N35-TBAND   check  0.201096      0.121106       0.6022  2671     <- the handover's 20.11 / 12.11
```
(`docs/lab/survivorship/roster-width-curve-2026-10-14.csv`)

M0139 holds **two** recorded 35-name variants, and the difference between them is the rules preset,
not the book:

| candidate | rules_id | max DD | CAGR | PF | DSR | eligible |
|---|---|---|---|---|---|---|
| `M0139-N35-EBAND` | `monthly-hold-frac-gotrade` | 0.19590 | 0.36913 | 2.088 | 0.9338 | **1** |
| `M0139-N35-TBAND` | `monthly-hold-frac-gotrade-tband` | 0.19602 | 0.37106 | 2.104 | 0.9435 | **1** |

`monthly-hold-frac-gotrade` is **the preset `RAW-FR-GT` runs today**. `…-tband` is the same preset
with `resize_basis="target"` (`sim/rules.py:282`) — the fix for the resize band that never fires
(`seer-resize-band-never-fires`). Both are dev-eligible; on dev they differ by 0.012 points of
drawdown and 0.19 points of CAGR.

M0139's own recorded verdict reads *"Twenty names still wins"*. It was written on the dev store
alone, before M0147 and M0152 showed the dev store is structurally blind to what width is for. The
verdict is a closed record and is not edited (CLAUDE.md: closed records are frozen); the roster
entry's admission note is where the correction is stated.

---

## Dependencies

### Configuration / Environment

| Name | Meaning | Where |
|---|---|---|
| `SEER_LAB_DB` | the lab database parallel sessions share | `lab/store.py` |
| `SEER_RESEARCH_STORE` | the dev store (`engine/.research`) | `commands/lab.py:209` |
| `SEER_RESEARCH_TEST_STORE` | the test-window store (`engine/.research-test`) — **not used by this plan** | `commands/lab.py:259` |
| `DATABASE_URL_UNPOOLED` | Neon, for `promote` and `migrate` | `.env` / Actions secrets |
| `PYTHONPATH=engine/src` | required when running engine code from a worktree | `seer-lab-stage-targets-the-main-checkout` |

### Research stores present on this machine

```
engine/.research        dev            (no manifest purpose)
engine/.research-sv     purpose: "survivorship-check"
engine/.research-test   test window    (no manifest purpose)
engine/.research-dv     dollar-volume universe
engine/.research-dv500  dollar-volume universe
```

All three stores this plan needs are present (`seer-survivorship-store-absent-here` — the note
saying `.research-sv` was gone was itself wrong).

### External Services

- Neon Postgres — the roster, the paper books, the nightly.
- Vercel — builds `main` only (`seer-vercel-only-main-deploys`).
- GitHub Actions `nightly.yml` — applies migrations, then runs the paper step.

---

## Why no worktree

`/analyze` cuts a worktree by default. Here it would be actively harmful, and the reason is a
property of this repo rather than a preference:

1. **`lab run` requires the method file to be committed, and the commit is the pre-registration.**
   A pre-registration on a feature branch is a pre-registration nobody can check until the branch
   lands, which is the opposite of what the mechanism is for.
2. **`lab/lab.sqlite` is a committed binary SQLite file.** Four method runs on a branch produce a
   `lab.sqlite` that cannot be merged with whatever `main` holds — there is no three-way merge for
   a binary, and the file is append-only by trigger, so "take theirs" silently discards trials.
3. **`lab stage` regenerates and stages `/home/miftah/seer` regardless of where it is run from**
   (`seer-lab-stage-targets-the-main-checkout`), because the editable install resolves
   `COMMITTED_DB` to the main checkout. A worktree does not isolate the artifact it exists to
   isolate.
4. **The research stores are not in worktrees** (`seer-research-store-not-in-worktrees`); every
   `--store` would have to point back at the main checkout anyway.
5. The repo's own practice agrees: every recent lab commit (`5ad3381`, `48c295f`, `4b38119`, …) is
   directly on `main`, and CLAUDE.md says "Once a change is verified, commit and push to `main`".

So the plans are pinned to **`main` @ `661870d`**, and every phase works in `/home/miftah/seer`.
The isolation that a worktree would have bought is replaced by two invariants in the plan: each
phase commits by explicit pathspec (never `git add -A`, never `reset --hard`), and the lab phases
serialise their `lab stage` + commit.

---

## Reference List

Every site that touches "the roster holds 20 names", or that a new roster entry must be declared
in. This is what phase 2's decomposition is built from.

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `RAW_GT_ID = "RAW-FR-GT"` | `paper/roster.py:172` | def | `paper` |
| `RESIDMOM_PARAMS` (bound to `M0007-N20-RAW`) | `paper/roster.py:371` | def | `paper` |
| `RESOLVER["RESIDMOM"]` | `paper/roster.py:479` | def | `paper` |
| `LAB_PROVENANCE[RAW_GT_ID]` | `paper/roster.py:639` | def | `paper` |
| `SEED_ROWS` entry `RAW-FR-GT` | `paper/roster.py:994–1016` | def | `paper` |
| `EVIDENCE["RESIDMOM"]` → `residmom_evidence` | `strategies/evidence.py:689`, `:411` | def | `strategies` |
| `MONTHLY_HOLD_FRAC_GOTRADE` | `sim/rules.py` (preset) | config | `sim` |
| `PINS` (spec digests) | `tests/test_paper_roster.py:~100–130` | test | `engine/tests` |
| `test_digests_are_pinned` | `tests/test_paper_roster.py:236` | test | `engine/tests` |
| migration-equality check | `tests/test_paper_roster.py:434` | test | `engine/tests` |
| roster id list | `tests/test_paper_store.py:63` | test | `engine/tests` |
| roster id list | `tests/test_paper_check.py:60` | test | `engine/tests` |
| roster id list | `tests/test_migrate.py:293` | test | `engine/tests` |
| `('RAW-FR-GT', …)` seed row | `db/migrations/017_roster_real_fees.sql:71` | config | `db` |
| gate-note update | `db/migrations/018_gate_note_recorded_n.sql:30` | config | `db` |
| `("RAW-FR-GT", …, "M0007-N20-RAW", …)` | `.claude/skills/calculate-assets/build_audit.py:14` | config | skill |
| `methodHref('RAW-FR-GT') === '/sera/methods/M0007'` | `web/lib/sera/paper.test.ts:11` | test | `web` |
| `paperOf('RAW-FR-GT')` | `web/lib/sera/paper.test.ts:48` | test | `web` |
| roster-change checklist | `docs/runbooks/paper-trading.md:53–86` | doc | `docs` |

Note what is **not** on this list: `backtest/registry.py`. `promote` never writes it — it is the
P7a dev-run candidate set, fixed before the run with `candidate_digest` pinned, and appending would
corrupt the multiple-testing count. A promoted method reaches the roster through the resolver.

---

## The four method ideas, as the lab already records them

All four are `idea`-status rows in `methods` with full hypotheses. The phase planners read those
rows; this section records only what the analysis established *about* them.

### M0155 — trim a holding falling apart while the market is fine (parent M0152)

The 2006 signature: SPY 3.71 → 3.62 (a 2% dip that made a new high by September) while the 20-name
book lost 21.8% on the check store. Across widths 20/25/30/35/45/50/70 the 2006 fall runs
21.8 / 18.9 / 18.8 / 16.2 / 15.1 / 14.8 / 12.9 — nearly nine points, against 3.6 points in 1998 and
none at all in the crisis years. Deliberately **not** a stop-loss: M0020 already showed a stop
fires on the market falls the gate has handled. The idea names three candidate shapes (a
market-relative trailing-return exit, a half-weight cut on own-entry drawdown while SPY is above
its 200-day line, and a mid-month rank-decile drop).

Prior art in the tree: `m0109_book_drawdown_brake.py` is the *book*-level version of the same
family and carries the shadow-index reconstruction, the `STEP` rounding and the `WARM` session
count. `m0035_relative_shortfall_brake.py` and `m0019`/`m0020` are the stop-loss line.

**The constraint that shapes the phase:** the idea says in its own words that promotion is not
available on this line unless the brake is hosted on a book whose ancestry is clean — M0007 is
test-failed-adjacent and the kin bar refuses the family. And it says the measurement must be read
**on both stores**, because the dev store cannot see the problem the brake is built to fix.

### M0156 — the roster's other book on the honest tape (parent M0152)

`MOM-FR-GT` is `M0002-REL-85`, a 20-name book, and it has **no row in
`docs/lab/survivorship/grid.csv` at all**. M0002's status is `test-failed`. Step one is
`lab survivorship M0002` — free, records nothing, moves no N and no look. Step two, conditional on
step one, is a width sweep in M0152's shape.

**What the analysis adds:** M0002's recorded trials must be checked for preset comparability
before step two is scoped — the idea itself flags that a cost model or share basis mismatch turns
step two into "mint a realistic twin first". And `Amendment` (`method.py:62`) is the mechanism that
lets step two be a second pre-registered batch under the same id, so the sweep costs no extra N.

### M0149 — the asymmetry book braked by its own falling account (parent M0133)

The open door: `M0133-N40` (the same asymmetry rank, **gate off**) reads 0.57 / 0.59 / 0.58 against
the three failed books — behaviourally free by a wide margin — and still earns +9.6%/yr against
SPY TR's +7.2%. Its only defect is a 69.1% fall. Every *market*-reading brake puts every book in
cash in the same months, which is exactly what D14 refuses; a *book*-reading brake does not.
Variants named by the idea: own-drawdown cuts at 15% and 25% below its own peak, own 63-day
volatility targeted at 14% and 16%, and both.

Prior art: `m0109_book_drawdown_brake.py` (the drawdown brake, including the ratchet warning —
reading the *braked* account is a ratchet and M0109 reads the unbraked shadow instead) and
M0001/M0002's own-vol scaling.

**The idea's own instruction, which the phase must honour:** measure the kin reading **first**, off
the recorded curves, before writing any analysis. `lab kin` (`ad49cf0`) does this without spending
an id. And `seer-behavioural-kin-reports-only-the-best-twin`: `behavioural_kin` reports one Twin
per *failed method*, not per variant, so a clean headline number does not clear every arm.

### M0148 — a time-lock on the switch (parent M0143)

M0143 found every DOWN arm lost in proportion to **how often it changed its mind**: time invested
fell monotonically with the window (72.7 / 70.7 / 62.1 / 49.2%) while turnover rose the other way
(5.37 / 5.20 / 5.65 / 6.40). The mechanism is hysteresis. M0101 already tried to buy it in the
*price* domain (bands) and lost. This buys it in the *time* domain: once the switch changes state
it may not change again for K monthly checks. K=0 is the paired control and must reproduce
`M0143-CALM-UP63` to the digit. Host: `M0088-C-LIVE-63`, chosen because its kin reads clean —
family `stock-dividend-change-drift` holds no test-failed method.

Machinery already in the tree: `m0113_trend_switch_reentry.py` expresses the switch's asymmetry
through `held` and exposes `entry_on` + `ReentryParams`; `m0143_quarter_return_exit.py` is the
direct parent. A time lock needs state the allocator does not have (how long since the last flip),
which is the one genuinely new mechanical question in this phase — see the phase plan.

---

## Impact Points (files that WILL need changes)

### R1 — the roster width change (phase 2)

1. `engine/src/seer_engine/paper/roster.py` — a new params constant bound to `M0139-N35-EBAND`, a
   new `RESOLVER` key, a new `LAB_PROVENANCE` entry, a new `SEED_ROWS` row, and `RAW-FR-GT` moved
   to `status="retired"` with its `paper_end`.
2. `engine/src/seer_engine/strategies/evidence.py` — one `EVIDENCE` key mapping the new resolver
   name to the existing `residmom_evidence`.
3. `db/migrations/021_roster_width_35.sql` — insert the new row, retire `RAW-FR-GT`, byte for byte
   what `promote --retire` writes, in `013`/`017`'s argued style.
4. `engine/tests/test_paper_roster.py` — a new `PINS` entry; `test_digests_are_pinned` and the
   migration-equality test must stay green **and no existing pin may move**.
5. `engine/tests/test_paper_store.py:63`, `test_paper_check.py:60`, `test_migrate.py:293` — the
   roster id lists.
6. `.claude/skills/calculate-assets/build_audit.py:14` — the roster id → lab variant map.
7. `docs/runbooks/paper-trading.md` — the roster table and the retirement record.

### R2–R5 — the four method runs (phases 1, 3, 4, 5)

8. `engine/src/seer_engine/lab/methods/m0148_*.py`, `m0149_*.py`, `m0155_*.py` — one new file each.
9. `engine/src/seer_engine/lab/methods/m0156_*.py` — only if step one's finding makes step two
   live; step one needs no file at all.
10. `lab/lab.sqlite` and `web/data/lab.json` — written by `lab run` / `lab note` / `lab stage`.
11. `docs/lab/survivorship/` — one dated CSV per survivorship or width measurement. **Never**
    appended to `grid.csv`: `survivorship_record.GRID_PATH` points the hard gate's D16 at that
    exact file, and appending would change which promotions the gate refuses as a side effect of a
    research run (handover decision, not to be reversed).

**This document describes. The plan files prescribe.**

# Plan: the lab exposure diagnostic — measure the picks, not the brakes

**Slug:** lab-exposure-diagnostic
**Date:** 2026-10-12 10:05:51 +07
**Analysis:** `docs/analyzer/20261012-100551-X4P9_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/lab-exposure-diagnostic`
**Branch:** `feature/lab-exposure-diagnostic` (base: `origin/main` @ `85f65bd`)
**Phases:** 2
**Status:** reconciled
**Coordinator:** —

---

## Why

The user's request, verbatim:

```
/analyze docs/plans/HANDOVER_20261012-picks-not-brakes.md

Plan and then build the target in §4.1: the exposure diagnostic that measures a method's own
picks separately from the spare money it parks in the market, then run it over the five
surviving kin-clean dev-eligible methods in §2 and journal the answer.

Read the whole handover first. The hard constraints are in §3 (it must be report-only: no trial
recorded, N unmoved, no test-window look, because N counts distinct methods and every new one
raises the luck hurdle for the whole lab retroactively) and §6 (lab stage, no mid-batch rebase,
Postgres for DB tests, no hard-gate override). §4.1 lists open design questions that are yours
to decide, not mine.
```

And the handover's own statement of the problem (§1, §2), which is the specification for what
this must be able to see:

> M0107 included a control arm that stripped the parked SPY out of the calm dividend raiser book.
> The result: the dividend picks filled only about four slots in ten; the rest of the money sat in
> SPY, timed by the 200-day switch. Measured with that parked money removed, **the picks lose to
> the market in every era** — behind 4.4 points a year in 1996–2002, ahead ~1 point in 2003–2008,
> behind 5.7 points from 2009. The timed SPY holding was worth about 9 points a year early on; the
> switch on top of it about 0.4.
>
> So a family of six methods and thirty-five variations, which the lab spent three batches tuning,
> never had a picking edge at all. … **Nothing in the lab would have caught this.** No method
> reports how much of its money is in its own picks, or what those picks did alone.
>
> **If the remaining four are also mostly parked market money, the lab has no live candidate at
> all, and should be told so plainly rather than discovering it one family at a time.**

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Build the §4.1 exposure diagnostic: report what share of a method's money was in its own picks (whole window and per era) versus parked in the market or in cash, and what the picks alone did against SPY TR per era with the parked holding removed and the brakes off | 1 |
| R2 | Run it over the five surviving kin-clean dev-eligible methods in §2 (M0024, M0028, M0030, M0044, M0053) and journal the answer | 2 |
| R3 | Hold the §3/§6 constraints: report-only — no trial row, no moments, N unmoved, no test-window look, nothing in `lab.sqlite` but a journal entry; `lab stage` for any database commit; no hard-gate override | 1, 2 |

R3 is a cross-cutting invariant, not a deliverable that can be split out: phase 1 must *make* the
path report-only and prove it in tests, and phase 2 must *keep* it so when it runs. Both phases
own it deliberately.

## Scope

**In scope**

- A new report-only lab subcommand, `lab exposure`, and the module behind it
  (`engine/src/seer_engine/lab/exposure.py`).
- A generic wrapper allocator that re-weights whatever a method's own allocator returns, so a
  method's picks can be priced apart from its parked money and its brakes, with **no change to any
  method file and no new method id**.
- Running it over the five live methods, reading the answer, and journaling it.

**Out of scope, and why**

- **`sim/`, `backtest/`, `strategies/`, `paper/`, `sean/`.** Nothing in the shared engine changes
  (Decision D10). Recorded results cannot shift if no code they ran through moves.
- **New lab methods.** Handover §3: `N` counts distinct methods and raises the luck hurdle for the
  whole lab retroactively. Not one new method id is minted.
- **The test window.** Not read, not named, not spent.
- **Backfilling all 130 methods.** Decision D4 — the command takes ids; phase 2 names five.
- **`web/`.** `lab stage` regenerates `web/data/lab.json` from the database; no TypeScript changes.
- **The idle-cash interest rule (§5.1), the store-rebuild guard (§5.2), EODHD (§5.3), the queued
  lab ideas (§5.5), the data jobs (§5.6).** All named in the handover as *later* or *not this*.

## Invariants

Every phase must hold all of these. They are the §3/§6 constraints restated as checkable rules.

1. **The tree builds and the suite passes at the end of each phase.**
   `engine/.venv/bin/ruff check engine` clean, and `pytest engine/tests` green with Postgres up
   (`PG_TEST_URL`) and no DB test skipping. From this worktree, tests run with
   `PYTHONPATH=<worktree>/engine/src` or they silently test the main checkout.
2. **Report-only.** The new path writes exactly one kind of row to `lab/lab.sqlite`: `insights`.
   No `trials`, `trial_moments`, `trial_funding` or `trial_provenance` row; no `methods.status`
   change; no `docs/lab/prereg/` file. Asserted by a test, and printed before-and-after by the
   command.
3. **N does not move.** `store.dev_trial_count(conn)` is identical before and after any run of
   `lab exposure`, and no new method file is created. No recorded method's DSR hurdle may change
   as a side effect of this work.
4. **The look budget does not move.** `store.test_looks(conn)` is identical before and after.
   `measure` refuses any store whose `window` is not `research.DEV_WINDOW`, and `dev.run_registry`
   is called with **no `window=` keyword**, so the D9 default binds.
5. **No shared engine code changes.** `git diff --stat origin/main` touches nothing under
   `engine/src/seer_engine/{sim,backtest,strategies,paper,sean,fundamentals}/`.
   `commands/lab.py` changes additively only (one docstring line, one subparser, one handler, one
   `_HANDLERS` entry) — no existing subcommand's behaviour, help text or output moves.
6. **No new method ids and no edits to existing method files.** `lab/methods/` is untouched.
   `lab next-id` returns the same id before and after.
7. **The hard gate is not routed around.** No flag, no environment variable, no `hardgate` edit.
   This path never promotes and never tests, so it never meets the gate; if it ever does, a
   refusal is a finding to record.
8. **Arms are compared with each other, never with the recorded trial.** Measured 2026-10-12:
   M0030-C50T re-runs to `9.583603` against a recorded `9.583723`, and its SPY TR to `3.466805`
   against a recorded `3.514206`. The reproduction check is printed as information, the way
   `lab costs` prints it; no conclusion may rest on a recorded number beside a re-run one.
9. **Any commit that contains `lab/lab.sqlite` was produced by `lab stage` and also contains
   `web/data/lab.json`.** CI fails a database commit without it.
10. **No mid-run `git pull --rebase`.** `git fetch` + `git merge --ff-only` only, and never while
    a run holds the database open.
11. **Plain language where the owner reads it.** CLAUDE.md's rule is "text the owner reads (site
    summaries, Sera pages) uses plain language: no ids, digests or code", and that is exactly how
    far it reaches here: **the lab journal** (the five observations and the synthesis, which are
    what `/sera` renders) carries no ids, digests, candidate suffixes or code. `docs/backtests/`
    is a **developer-facing record** and follows its own existing convention — dated
    `YYYY-MM-DD-slug.md` with a committed companion `-grid.csv`, and ids are allowed, as
    `2026-10-08-how-many-names.md` already uses them. Its opening short-answer paragraph is still
    plain English and id-free, because that paragraph is the one the owner reads. The terminal
    report may use ids throughout.
12. **Prose docstrings that explain *why*.** New modules match the surrounding style
    (`lab/real_costs.py`, `lab/survivorship_check.py` are the models).

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | `lab exposure`: the diagnostic | R1, R3 | `engine/src/seer_engine/lab`, `engine/src/seer_engine/commands` | 3 | — | HARD | `.workflows/plan/lab-exposure-diagnostic/phase-1.md` | — | — |
| 2 | Run it over the five, and journal the answer | R2, R3 | `lab/`, `docs/`, `web/data` | 5 | 1 | NORMAL | `.workflows/plan/lab-exposure-diagnostic/phase-2.md` | — | — |

### Phase 1 — `lab exposure`: the diagnostic

**Satisfies:** R1, R3
**Owns:**
- `engine/src/seer_engine/lab/exposure.py` (new) — the park-set rule, the `ExposureAllocator`
  wrapper and its params, the four arm builders, `plan_methods`, `measure`, the era table,
  `format_report`, `summary_line`, `insight_text`, `journal`.
- `engine/src/seer_engine/commands/lab.py` (additive edit) — one module-docstring line, one
  `sub.add_parser("exposure", ...)` block, one `_exposure(conn, args)` handler, one `_HANDLERS`
  entry.
- `engine/tests/test_lab_exposure.py` (new).

**Does not touch:** `sim/`, `backtest/`, `strategies/`, `paper/`, `sean/`, `fundamentals/`,
`lab/methods/`, `lab/hardgate.py`, `lab/runner.py`, `lab/store.py`, `web/`, `db/`, the lab
database itself, any existing subcommand's behaviour or help text.

**Exit criteria:**
- `lab exposure --help` renders (the `%%` escaping rule holds) and `lab exposure M0030` runs on
  the real dev store, printing four arms per variant and the per-era grid.
- `ruff check engine` clean; `pytest engine/tests` green with Postgres up, no DB test skipping,
  and the new test file covers: the wrapper's `Allocator` contract (via `allocatorkit`), the
  re-weighting arithmetic, every refusal that must land before a store loads, the test-window
  refusal, and the report-only invariant (N, looks and every trial-side table unchanged across a
  full CLI run on the smoke fixture).
- `git show --stat HEAD` lists exactly the three files above, and
  `git diff --name-only origin/main -- engine/ lab/ web/ db/ docs/backtests/ .workflows/todos.md`
  shows the same three and nothing else. (An unpathspec'd diff against `origin/main` also shows
  the planning artifacts — this plan index, the two phase plans and the analysis file — which are
  expected differences, not scope creep. See Reconciliation Log C6.)

### Phase 2 — Run it over the five, and journal the answer

**Satisfies:** R2, R3
**Owns:**
- `lab/lab.sqlite` — five `observation` entries (one per method) and one `synthesis` entry.
- `web/data/lab.json` — regenerated by `lab stage`, committed with the database.
- `docs/backtests/2026-10-12-exposure-diagnostic.md` (new) — the write-up and the full grid. The
  name follows the directory's existing convention (`2026-10-08-how-many-names.md`).
- `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` (new, **committed**) — the
  machine-readable variant x arm x era grid, written straight there by `lab exposure --csv`, the
  way `2026-10-08-how-many-names-grid.csv` sits beside its write-up.
- `.workflows/todos.md` — the task record.

**Does not touch:** any Python source. Phase 2 runs the command phase 1 built and writes prose
and journal rows. If the run exposes a bug, phase 2 reports it and stops rather than editing
phase 1's module — a fix is a follow-up commit, not a silent amendment to a finished phase.

**Exit criteria:**
- `lab exposure M0024 M0028 M0030 M0044 M0053 --store /home/miftah/seer/engine/.research --csv
  docs/backtests/2026-10-12-exposure-diagnostic-grid.csv` has run to completion against the main
  checkout's research store, and that CSV is committed. (`--only IDS`, alias `--candidate`, and
  `--no-journal` are the other flags phase 1 froze; phase 2 uses neither.)
- The before/after line in its own output shows N and the test-window looks unchanged, and a
  direct `sqlite3` count of `trials`, `trial_moments`, `trial_funding` and `trial_provenance`
  agrees.
- Five observations and one synthesis are in the journal, in plain words, naming no ids.
- `lab stage` has run; the commit carries `lab/lab.sqlite` **and** `web/data/lab.json`.
- `docs/backtests/2026-10-12-exposure-diagnostic.md` answers the §2 question in one plain-English
  paragraph at the top — do the four non-core methods have a picking edge, or is the lab's live
  space empty? — and links its committed grid companion. Its body and tables may name ids.

---

## Design

This section is the contract both phases plan against. It is the answer to §4.1's four open
questions plus everything they implied.

### The four arms

For one recorded dev variant, four runs of the **same** allocator on the **same** window, at the
**same** recorded capital and funding, differing only in how the allocator's targets are
re-weighted on the way out:

| Arm id suffix | Transform on the inner allocator's targets | What it prices |
|---|---|---|
| (none — the recorded variant) | identity: the candidate is used unchanged | the reference, and the reproduction check |
| `-PICKS` | drop every target whose symbol is in the park set; **keep the survivors' weights** | the pick sleeve as the method sized it. Its `RunStats.exposure` **is** the share of the book that was ever in its own picks |
| `-FULL` | drop the parked targets, then rescale the survivors so Σ weight = 1 | the picks with the brakes off and the whole book behind them — the fair selection test against SPY |
| `-PARK` | keep **only** the parked targets, rescaled so Σ weight = 1 | what the spare money in the market did, priced on its own |

`-PARK` is built **iff the inner allocator's `holds()` is non-empty** — not merely when the park
set is non-empty. A re-weighting can only keep what the allocator actually targets, and an idle
instrument is never a target (the runner places it, not the allocator), so for a method that parks
only there the parked arm would be an all-cash book. The report says so in a sentence rather than
printing a blank column.

The `-PICKS` / `-FULL` pair is the point: `-PICKS` carries the cash drag the method really had,
`-FULL` removes it. Together they bracket the truth without either one being a lie, which is why
both exist rather than one being chosen. For a method whose only "brake" is a volatility target
(M0044, M0053) there is no park set at all, and `-FULL` is precisely "the same picks with the
brake switched off" — the handover's title, *measure the picks, not the brakes*.

### The park set

```
park(candidate) = set(candidate.allocator.holds(candidate.params))
                  | ({candidate.rules.idle_symbol} if candidate.rules.idle_symbol else set())
```

That formula is what `exposure.park_set` computes, and the two halves of it have **different
jobs**, which is the part worth saying plainly:

- **`holds()`** is the half a re-weighting can act on. It is an existing, mandatory `Allocator`
  member that every allocator in the repo already maintains, and it already means exactly this:
  `dev.candidate_owner_inputs` reads it to decide which ETFs the owner must be able to buy.
  `BLEND` unions its parts', `VOLTARGET` delegates to its inner, `f_index.TIMING` returns the
  symbol it holds, and M0107 returns the market symbol exactly when `park=True`. So the detection
  is generic and needs no per-method declaration (Decision D2). It is also the test for whether a
  `-PARK` arm exists at all (Decision D15).
- **`rules.idle_symbol`** is parked money too, but it never appears as a target — the runner, not
  the allocator, puts the residual weight there (`book_runner._with_idle`, which raises if an
  allocator targets it). So it is never dropped by the re-weighting; instead the three constructed
  arms run with it **switched off** (`arm_rules`), and their freed weight is cash. Re-parking freed
  weight into an index instrument would measure nothing (Decision D14). An idle symbol on its own
  therefore never justifies a `-PARK` arm.

No lab method sets `idle_symbol` today — checked 2026-10-12 across `lab/methods/` — so for every
method this can currently be pointed at, `park_set` is `holds()` and `arm_rules` is a no-op.

### What cannot be undone, and is reported instead

A gate that fires by returning **no targets at all** empties the book, and no re-weighting wrapper
can invent the basket a gated-off allocator would have produced. The diagnostic therefore reports,
per arm, the **share of decision sessions on which the inner allocator returned nothing** — a
first-class number in the grid — rather than faking a gate-free counterfactual (Decision D3). For
M0024, whose trend gate is worth ~25 points of exposure (`SAME-N20` 0.652 vs `NOTREND` 0.898),
that number is the honest half of the answer.

### The era table

Eras, exactly M0107's split, because that is the split that exposed the problem (handover §4.1):

| Era | Range |
|---|---|
| whole window | the candidate's own `candidate_window` start .. `DEV_END` |
| 1996–2002 | 1996-01-01 .. 2002-12-31 |
| 2003–2008 | 2003-01-01 .. 2008-12-31 |
| 2008 | 2008-01-01 .. 2008-12-31 (deliberately inside the one above) |
| 2009–2015 | 2009-01-01 .. 2015-10-16 |

**Whole-window** numbers come from the `DevRow`: the money-weighted return when the run was
funded, the CAGR otherwise, against `row.spy_tr`'s same measure — which `dev._run` already makes
deposit-matched by feeding `spy_curves` the run's own `cashflows` on the run's own sessions.

**Per-era** numbers come from `lab.walkforward.measure(curve, era_start, era_end, deposits)` on
the arm's own `month_end_curve(result.snapshots)`, with `deposits` from
`hardgate.trial_deposits(conn, trial, curve)` — so a funded curve is de-funded *before* it is cut,
and the owner's own deposits are never counted as edge. The per-era benchmark is the recorded
`REF-SPY-HOLD` curve from `hardgate.geometry(conn).bench`, sliced the same way. This is the path
`lab survivorship` already uses for its 2009–2015 lead; a second reconstruction would be a second
chance to read a deposit as edge (Decision D7).

The headline per era is the **lead**: the arm's de-funded CAGR minus SPY's over the same slice, in
points a year. Leads are comparable across methods; absolute returns are not, because the five
methods did not all run funded.

### Journal

One `observation` per method and one `synthesis` for the batch, in plain words with no ids
(Decision D9; `INSIGHT_KINDS` at `lab/store.py:115`). `--no-journal` prints and writes nothing at
all, mirroring `lab survivorship`.

---

## Reconciliation Log

One row per conflict found across the two plan files and this index, with what was changed.

| # | Conflict | Class | Phases | Resolution |
|---|---|---|---|---|
| C1 | Phase 2's command lines were written before phase 1's plan existed, and its own Step 0 said so — the plan *depended* on reading `--help` to learn the flags | Contract drift | 1, 2 | Phase 1's frozen surface (`lab exposure M0030 [M0024 ...] [--only IDS] [--store DIR] [--csv PATH] [--no-journal]`, alias `--candidate`, exit 0/2/1) is now quoted verbatim in phase 2's **Requires**, and every command in phase 2 cross-checked against phase 1's subparser and `_exposure` handler. They matched; only the `--csv` target moved (C2). Step 0's `--help` read is kept as belt and braces but is explicitly no longer the source of the commands, and a drift it finds is now a finding to report, not a licence to improvise |
| C2 | Phase 2 named its write-up `20261012-exposure-diagnostic.md` and left the grid CSV in `/tmp`; `docs/backtests/` convention is `YYYY-MM-DD-slug.md` with a committed `-grid.csv` companion | Gap (convention) | 2 | Renamed to `docs/backtests/2026-10-12-exposure-diagnostic.md`; `--csv` now points straight at `docs/backtests/2026-10-12-exposure-diagnostic-grid.csv`, which is committed. Updated across phase 2 (contract, Files table, Steps 3, 5, 6, 9, 10, Verification, exit criteria, Handoffs, Rollback), phase 1's example command, and this index (Phases table file count 4 -> 5, phase-2 Owns, phase-2 exit criteria, Rollback) |
| C3 | This index's invariant 11 said the `docs/backtests/` write-up may carry no ids; phase 2 over-complied with fixed plain-English labels for all five methods and four arms and flagged the clash with the existing files there, which do use ids | Contract drift (index vs CLAUDE.md) | 2 | Invariant 11 narrowed to what CLAUDE.md actually says — the lab journal and Sera pages. `docs/backtests/` follows its own convention and may use ids; the write-up's opening short-answer paragraph stays plain English and id-free. Phase 2's Step 6 language rule and its Verification grep rewritten to check that paragraph alone, with a new grep added over the journal rows, where the rule does bind. Rung 5 (the user's CLAUDE.md rule as written) over rung 1 (this index's over-broad restatement) |
| C4 | Phase 1 settled five forks inside its own boundary that appeared in no Decisions table, so no later reader could see them | Gap (undocumented decision) | 1, 2 | Promoted to **D13–D17** with rungs: bracket variants refused pre-load; `idle_symbol` stripped from the constructed arms; `-PARK` built iff `holds()` is non-empty; the recorded arm runs unwrapped (so `empty_share`/`mean_names` are None on that column); a purpose-marked store allowed, only a non-dev window refused. Checked phase 2 against each — it contradicts none |
| C5 | This index's Design stated the park set as `holds() \| {idle_symbol}` with no account of the idle symbol's different role, which read oddly beside phase 1's "`-PARK` iff `holds()` is non-empty" and its idle-stripping | Contract drift (index vs plan) | 1 | Formula kept — it is what `exposure.park_set` computes — and the Design section now says plainly that `holds()` is the half a re-weighting acts on (and the test for whether `-PARK` exists at all), while `idle_symbol` is never a target and is instead switched off in the three constructed arms. The `-PARK` sentence in the arms table now matches phase 1 word for word |
| C6 | Phase 1's exit criterion "`git diff --stat origin/main` shows exactly three files" is not checkable: the branch also carries the plan index, the two phase plans and the analysis file | Contract drift (uncheckable criterion) | 1 | Replaced with two checks that are: `git show --stat HEAD` lists the three files, and `git diff --name-only origin/main` **pathspec'd** to `engine/ lab/ web/ db/ docs/backtests/ .workflows/todos.md` shows the same three. The planning artifacts are named as expected differences |
| C7 | Phase 2's Step 0 runs `lab exposure --help` and the suite before taking its baseline, but a `lab` subcommand migrates `lab/lab.sqlite` on connect — the "nothing moved" evidence could have been taken against an already-dirtied file | Gap | 2 | Step 0 now ends with `git status --short lab/lab.sqlite && git checkout -- lab/lab.sqlite`, so Step 1's blob check and Step 2's read-only baseline are both taken against the committed copy. Phase 1's Verification already handled the same hazard for its smoke run |
| C8 | Risk that phase 2 conflates the lab's N (354 dev trials) with the 358 total trials, and that its `insights 184 -> 190` assumed more journal rows than the command writes | — (checked, no change needed) | 2 | Verified against phase 1's `_exposure`: `entries = [exp.journal(conn, rep) for rep in reports]` writes **exactly one `observation` per method and nothing else**, so 184 -> 189 at Step 3 and -> 190 after the hand-written synthesis at Step 7 — as phase 2 states. Phase 2's baseline table already separates `trials` 358, `dev_trials_N` 354 and `test_looks` 4 correctly, and `store.dev_trial_count` is literally `count(*) FROM trials WHERE window='dev'`, so the number the command prints is the same 354 phase 2 checks. The one-observation-per-method guarantee is now written into phase 2's **Requires** so it cannot drift |

## Decisions

Every open question §4.1 handed the planner, settled here so neither phase meets a fork. The rung
is the precedence ladder: 1 stated invariant · 2 phase exit criteria · 3 the plan's code blocks ·
4 the index's Why and Requirements · 5 the user's raw input · 6 surrounding convention.

| Fork | Chosen | Rung |
|---|---|---|
| D1: a new `lab` subcommand, or an extension of an existing one? | **A new one, `lab exposure`**, modelled on `lab survivorship` (multi-method, report-only, `--csv`, `--no-journal`). `lab costs` answers a fee question and `lab names` a concentration question; folding a third into either would muddy both reports. | 5: the user's input makes this the planner's call, settled on 6: `lab costs`, `lab names` and `lab survivorship` are each their own report-only subcommand |
| D2: can "parked" be detected generically, or must it be declared per method? | **Generically**, from `set(allocator.holds(params)) \| {rules.idle_symbol}`. Every allocator already implements `holds()` and it already means "fixed instruments this allocator may hold" — `dev.candidate_owner_inputs` reads it that way. No method file changes. | 6: the existing `Allocator` protocol and its one existing reader |
| D3: reuse the method's own allocator with gates disabled, or give each method a hook? | **A generic wrapper allocator** that re-weights whatever the inner returns. Per the handover, adding variant arms to five methods would cost five method ids and the §3 N inflation, so a generic path is explicitly preferred. A gate that returns `()` cannot be undone generically; the share of sessions it fired on is reported instead of faked. | 5: the user's input ("prefer a generic path") |
| D4: backfill all 130 methods, or only the live five? | **Only what is named on the command line.** Phase 2 names the five of §2. A backfill is one command away later and costs nothing now. | 4: the Why section's §2 framing — the five are the live space |
| D5: which variant of each method? | **Every recorded dev variant**, as `lab survivorship` does, with a headline for the summary line = the best recorded **eligible** variant by MAR, falling back to the best by MAR when none is eligible (M0024 and M0030 have none). Measured: one run is 1.8–5.4 s, so 23 trials × 4 arms is minutes. | 6: `lab survivorship`'s shape, affordable because the cost was measured rather than guessed |
| D6: what capital and funding do the arms run on? | **The recorded trial's**, via `runner.recorded_capital` and `runner.recorded_contributions` — all four arms of one variant share them. Re-running a recorded trial on the wrong funding or capital is not the same measurement (`lab/runner.py:114-150`). | 6: the rule both `lab costs` and `lab survivorship` already obey |
| D7: what is the benchmark, per era? | **Whole window:** the run's own deposit-matched SPY TR from the `DevRow` (money-weighted when funded). **Per era:** the arm's de-funded monthly curve against the recorded `REF-SPY-HOLD` curve, through `wf.measure`. | 6: `survivorship_check.side_of`'s existing `era_yearly` / `era_spy_yearly` |
| D8: which eras? | **1996–2002, 2003–2008, 2008 alone, 2009–2015**, plus the whole window. | 5: §4.1 names this split, "because that is the split that exposed the problem" |
| D9: journal a note, an insight, or nothing? | **One `observation` per method plus one `synthesis` for the batch**, in plain words with no ids. `--no-journal` writes nothing at all. | 5: §4.1 allows "a note or insight"; 6: `lab survivorship`'s one-observation-per-method shape |
| D10: instrument `run_book` to record per-session holdings, for an exact picks/parked/cash split? | **No.** The share of money in the picks is the `-PICKS` arm's own `RunStats.exposure` — the same quantity M0107's session reported (HOST 70.4% invested, NONE 41.9%), which §4.1 cites as its evidence that this is computable. So nothing in `sim/` or `backtest/` moves and no recorded result can shift. | 5: §4.1's own evidence paragraph; 1: invariant 5 |
| D11: the arms' whole-window gate labels (`DevRow.failed`, eligibility, DSR) | **Not reported.** The arms are measurements, not candidates: they are never eligible, never promotable and never scored for luck. Printing a `failed` list beside them would invite exactly the reading invariant 3 forbids — that an arm is a result the lab holds. | 1: invariants 2 and 3 |
| D12: whether the `-FULL` rescale is capped when few picks survive | **Uncapped**, and the mean number of names held is printed beside it. A cap would be an invented parameter; the concentration is a real property of "what the picks did", and the `-PICKS` arm beside it shows the un-rescaled version. | 3: the Design section's arm table |
| D13: a bracket-engine variant — measure it, or refuse it? | **Refused, before the store loads.** `sim.rules.is_bracket` rules decide through the bracket engine, whose strategies are not `Allocator`s and expose no target weights, so there is no pick-versus-parked split to make. `plan_method` raises `store.LabError` (exit 2) naming the rule, and does it during planning so nothing pays for a 10 s store load to fail. | 6: the `Allocator` protocol — only allocator candidates have targets to re-weight; 3: phase 1's `park_set` / `plan_method` code blocks |
| D14: do the constructed arms keep `rules.idle_symbol`? | **No — stripped** (`arm_rules` returns `replace(rules, idle_symbol=None)`). An idle instrument *is* parked money: `book_runner._with_idle` puts whatever weight the allocator left over into it, so a `-PICKS` arm that freed the parked weight only to have the runner re-park it in an index instrument would measure nothing. The freed weight is cash instead. The **recorded** arm keeps its rules exactly as they were, because it is the reproduction check. Verified a no-op for the five: no lab method sets one today. | 4: the Why — the whole point is to price the picks apart from the parked money; 3: phase 1's `arm_rules` code block |
| D15: when is a `-PARK` arm built? | **Iff `allocator.holds(params)` is non-empty**, not merely when the park set is. A re-weighting can only keep what the allocator targets, and the idle symbol is never a target, so a park set that is only an idle symbol would yield an all-cash column. The report says so in a sentence instead. | 3: phase 1's `arms_for` code block; 6: `book_runner._with_idle`, which raises if an allocator targets the idle symbol |
| D16: does the recorded arm run through the wrapper? | **No — unwrapped.** The recorded column is the candidate exactly as the lab ran it, so it is a true reference and its reproduction check is honest; wrapping it in identity would put a layer between the lab's number and this one. The consequence is explicit: `empty_share` and `mean_names` are `None` on that column only, because the `Tally` lives on the wrapper. | 1: invariant 8 — the reproduction check is only meaningful against an unmodified run |
| D17: is a purpose-marked research store refused, as `lab survivorship` refuses one? | **Allowed, and named in the report.** `lab survivorship` compares numbers across *two* stores, where a marker means the two are not comparable. Here all four arms are measured on **one** store and compared only with each other, so a marked store is internally consistent. Only a non-dev `window` is refused — twice, on load and again in `measure` — which is what protects the look budget. | 1: invariant 4 (the window, not the marker, is what must be refused); 3: phase 1's `load_dev_store` code block |

## Open Questions

None. Every fork §4.1 raised, and every one reconciliation surfaced, is settled in **Decisions**
above. None is irreversible: each is one commit to change, and the diagnostic records no trial, so
nothing it decides can be baked into the lab's permanent record. Every `R` in the Requirements
table is owned by at least one phase, and every impact point in the analysis is owned.

## Rollback

- **Phase 1:** `git revert` the commit, or delete `engine/src/seer_engine/lab/exposure.py` and
  `engine/tests/test_lab_exposure.py` and undo the four additive hunks in `commands/lab.py`.
  Nothing else in the engine references the new module, so removal is total.
- **Phase 2:** the journal is append-only by trigger — an entry cannot be deleted or rewritten.
  A wrong reading is corrected the way the lab corrects every reading: a **new** insight that says
  so, and a note on the method. `docs/backtests/2026-10-12-exposure-diagnostic.md`, its
  `-grid.csv` companion and `.workflows/todos.md` revert normally.
- **The whole set:** `git branch -D feature/lab-exposure-diagnostic` and
  `git worktree remove /home/miftah/.worktrees/seer/lab-exposure-diagnostic` before phase 2 runs.
  After phase 2 has written to `lab/lab.sqlite`, the database rows are permanent by design; the
  code is still fully revertible.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/LAB_EXPOSURE_DIAGNOSTIC_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f docs/plans/LAB_EXPOSURE_DIAGNOSTIC_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan docs/plans/LAB_EXPOSURE_DIAGNOSTIC_PLAN.md

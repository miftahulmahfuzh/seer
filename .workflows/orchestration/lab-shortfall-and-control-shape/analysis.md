# Code Analysis: lab shortfall decomposition and control-shape check

**Type:** Feature Implementation
**Date:** 2026-10-19 11:05:02
**Session ID:** 20261019-110502-S4KQ
**Plan:** `docs/plans/LAB_SHORTFALL_AND_CONTROL_SHAPE_PLAN.md` (4 phases)
**Worktree:** `/home/miftah/.worktrees/seer/lab-shortfall-and-control-shape`, branch
`feature/lab-shortfall-and-control-shape` (base `origin/main` @ `ad8792d`)

---

## User Input

### Original User Request

```
lab feature

Read docs/plans/HANDOVER_20261019-the-placebo-is-a-control-not-a-constant.md first — it is your
brief, written by the session that found the problem. Sections 1 and 2 carry the evidence; the
section "The task for the next session" at the bottom is the scope.

Build: (1) a shortfall decomposition that splits any trial's gap to SPY TR over an era into gate
premium, fee drag, pool and residual weighting — the inputs are already in the trials row
(exposure, turnover, curve_json, spy_tr_cagr); (2) a control-shape check that compares a
placebo/control arm's trade count and turnover against the arm it controls and refuses or loudly
flags a mismatch; (3) as a small phase, the PIPESTATUS / duplicate-note fix in section 5.

The motivating case is trial n=828 (M0244-PLACEBO30): the lab published its 2009-2015 shortfall as
an 8.2 pt "equal-weight handicap" when the arm also carries the SPY-200 gate at 0.692 exposure, 15
turns/yr of fees, and a top-50 momentum pool. The decomposition must be able to answer whether any
of that 8.2 is actually weighting.
```

### User-Provided Context

The brief is `docs/plans/HANDOVER_20261019-the-placebo-is-a-control-not-a-constant.md`, written by
the session that reviewed the Sera `20261019-1014` batch. Its binding section is **"The task for
the next session"**:

> **Build the tooling that makes §1 and §2 impossible to repeat.** Two pieces:
> 1. **A shortfall decomposition** — given any trial, split its gap to SPY TR over an era into
>    *gate premium* (exposure × era return), *fee drag* (turnover × cost model), *pool* and
>    *residual weighting*. Today the lab reports one number and the residual gets named after
>    whichever ingredient the author was thinking about. The components are already in the row
>    (`exposure`, `turnover`, `curve_json`, `spy_tr_cagr`).
> 2. **A control-shape check** — when a method declares a placebo/control arm, compare its trade
>    count and turnover against the arm it controls and refuse or loudly flag a mismatch. M0230 and
>    M0248 are the two cases it would have caught; `seer-placebo-matched-to-a-books-exact-shape`
>    and `seer-placebo-sticky-vs-redrawn` are the written rules it would enforce.
>
> Fold in the `PIPESTATUS` / duplicate-note fix from §5 as a small phase.
>
> **Done means:** a decomposition command exists and is run on trial 828, the 8.2 figure is either
> confirmed with its components named or retired from the memory note, insight 461 and the `/sera`
> page; a mismatched control arm fails loudly; and `lab note` cannot double-append.

The handover also binds the rules from `CLAUDE.md`: closed records are frozen, the lab is committed
by index through `lab stage`, tests must not reach production, `%` is escaped as `%%` in argparse
help.

### User-Provided Files

None marked `@`. The brief named one file, read in full:
`docs/plans/HANDOVER_20261019-the-placebo-is-a-control-not-a-constant.md`.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | A shortfall decomposition: split any trial's gap to SPY TR over an era into gate premium, fee drag, pool and residual weighting, from inputs already in the trials row. Run it on trial 828 and answer whether any of the 8.2 pts is weighting. |
| R2 | A control-shape check: compare a placebo/control arm's trade count and turnover against the arm it controls, and refuse or loudly flag a mismatch. It must catch M0230 and M0248. |
| R3 | The `PIPESTATUS` / duplicate-note fix from handover §5: `lab note` must not be able to double-append an identical analysis. |

---

## Detailed Requirements Understanding

### Problem statement

The lab publishes a single number — "this trial trailed SPY TR by N points a year over this era" —
and whoever writes the analysis names that number after whichever ingredient they happened to be
thinking about. For trial 828 (`M0244-PLACEBO30`) that name was "equal-weight handicap", and it was
promoted from one matched pair's shortfall into a universal constant: insight 461, memory note
`seer-equal-weight-shape-costs-8pts-since-2009`, and the `/sera` synthesis page all now carry it.

The arm that produced the number is a gated, 15-turns-a-year, top-50-momentum book. Three
ingredients the name does not mention are inside the 8.2.

The second failure is the mirror of the first: when a method declares a control arm whose job is to
be the real book's shape with none of its identity, nobody checks that the shape actually matches.
`M0248-R` trades 3.6× the book it controls and pays ~15 extra turns of fees a year, so the "the
signal beats the blind draw by 3.6-13.5 pts" claim is quoted against a handicapped opponent.

### Success criteria

**R1.** A `lab shortfall` report exists. Given a trial (by `n` or by candidate id) and an era, it
prints the gap to SPY TR for that era and splits it into named, separately-computed terms that sum
back to the gap, with the residual explicitly labelled as a residual rather than as a cause. It is
run on trial 828 and its output either confirms the 8.2 with its components named, or retires it.

**R2.** A control-shape check exists; it flags `M0230-C50-R` and `M0248-R`, passes
`M0244-PLACEBO30` and `M0241-STALE`, and binds somewhere a researcher cannot miss it.

**R3.** A second `lab note --file` with the same body cannot silently append a second copy.

### Key considerations and measurements taken during this analysis

Everything in this section was **measured** against the committed lab and the dev store during the
analysis, not estimated.

**(a) The 8.2 reproduces exactly from recorded rows.** Running `walkforward.measure` on trial 828's
`curve_json`, de-funded through `hardgate.trial_deposits`, against `REF-SPY-HOLD` sliced the same
way over 2009-01-01..2015-10-16:

```
M0244-PLACEBO30  2009-2015  me  8.36%  spy 16.60%  gap  -8.24 pts/yr
M0244-FRESH30    2009-2015  me  8.77%  spy 16.60%  gap  -7.83
M0244-STALE30    2009-2015  me 12.30%  spy 16.60%  gap  -4.30
M0248-R          2009-2015  me 17.70%  spy 16.60%  gap  +1.09
M0248-D100       2009-2015  me 39.86%  spy 16.60%  gap +23.26
```

So the decomposition needs **no new measurement path**: `lab/walkforward.py:measure` +
`backtest/regime.py:defunded` + `lab/hardgate.py:trial_deposits` already produce the number being
decomposed, and they are the same path `lab exposure`, `lab gate` and `lab survivorship` use for
their era leads. A second reconstruction would be a second chance to read a deposit as edge.

**(b) `trials.exposure` is whole-window, and using it for an era is the decomposition's single
largest error term.** There is no per-era exposure anywhere in the schema (`trials`,
`trial_moments`, `trial_provenance`, `trial_funding` all checked). Measured from `SPY` bars in
`engine/.research/bars.csv`, the share of sessions on which SPY closed above its own 200-day mean:

```
whole      71.2%
1996-2002  64.0%
2003-2008  68.8%
2009-2015  80.6%     <-- the era the 8.2 is quoted over
```

Trial 828 records `exposure` 0.692 against a whole-window gate-on share of 0.712 — the book is
~97% invested whenever the gate lets it in. Applying the recorded 0.692 to 2009-2015 therefore
prices the gate at `(1-0.692) x 16.60 = 5.11` pts/yr, while scaling it by the era's own gate-on
share — `0.692 x (0.806/0.712) = 0.783` — prices it at `(1-0.783) x 16.60 = 3.60` pts/yr. A 1.5 pt
difference on an 8.2 pt headline. This is not a footnote; a decomposition that silently uses the
whole-window number mislabels a fifth of what it is decomposing.

**(c) The fee model is already written and does not need re-deriving.** `lab/turnover.py` prices
every order through `sim/costs.py:fee_parts` and already owns the floor transient. `trials.turnover`
is defined in `backtest/book_runner.py:699` as *sum of fill notionals (buys and sells) / mean
session equity / years*, so it is a per-dollar-of-notional quantity and composes directly with a
per-dollar fee rate. Measured through `turnover.round_trip` at the owner's funding and 30 names:

```
month   0  slot $  18.68  round trip $ 0.27  per-$-notional 0.7226%
month  24  slot $ 242.89  round trip $ 1.45  per-$-notional 0.2985%
month 120  slot $1139.70  round trip $ 5.81  per-$-notional 0.2549%
month 236  slot $2223.34  round trip $11.11  per-$-notional 0.2498%
```

The 2009-2015 era sits at months ~156-236 of the dev window, well past the floor, so the settled
rate ~0.25% applies: `15.05 x 0.2498% = 3.76` pts/yr for trial 828, against `3.57 x 0.2498% = 0.89`
for `M0244-STALE30`. The 2.87 pt difference the model predicts between those two arms is against an
observed gap difference of 3.94 pts (-8.24 vs -4.30) — the fee term carries most of it, which is
the first independent check that the model is not nonsense.

**(d) The headline answer, computed during this analysis.** For trial 828 over 2009-2015:

```
gap to SPY TR                              -8.24 pts/yr
  gate premium  (1-0.783) x 16.60           -3.60      era-scaled exposure
  fee drag      15.05 x 0.2498%             -3.76
  pool + weighting residual                 -0.88
```

> **Superseded 2026-10-19 by the reconciler, on the fee term only.** The `0.2498%` above is the
> rate at **one** month offset (month 236). Phase 1 measured the **mean rate over the era's own
> month offsets** (156..237), which is `0.251041%`, and resolved the era exposure to `0.7836`
> rather than `0.783`. The reconciled headline — the one every plan file, the backtest note and
> the exit criteria quote — is therefore:
>
> ```
> gap to SPY TR                                  -8.24 pts/yr
>   gate premium  (1 - 0.784) x 16.60%           -3.60
>   fee drag      15.05 turns x 0.2510%          -3.78
>   pool + weighting residual                    -0.87
> ```
>
> The 0.02 pt move changes nothing the plan rests on: the gate and the fees still account for 7.4
> of the 8.2, and pool and weighting together are still bounded under one point a year. **The name
> count is not the cause.** Trial 828's recorded configuration reads
> `params=GestureParams(window_days=380,top=30,...,screen=FactorParams(...,top=1000,...))`, and
> `shortfall.names_in` takes the shallowest bracket depth carrying a `top=`, so it resolves **30**,
> not the `DEFAULT_NAMES` fallback of 20. (Measured either way the term barely moves: the drag at
> 10 / 20 / 30 / 50 names is 3.71 / 3.74 / 3.78 / 3.85 pts/yr.)

So **the gate and the fees together account for roughly 7.4 of the 8.2, and pool and weighting
together are bounded under one point a year.** The handover's prediction — "the residual
attributable to weighting is near zero" — holds, and the published "8.2 pt equal-weight handicap"
is retired by the arithmetic rather than by argument. The plan requires the phase to reproduce
this, not to take it on trust from here.

**(e) `pool` cannot be computed from one row, and the decomposition must say so.** Nothing in the
row names the pool the book was drawn from. The only honest split is a *peer* split: a sibling arm
that shares the pool, the gate and the frame isolates the pool term by subtraction. So the
decomposition reports gate, fees and **one combined pool+weighting residual** by default, and
splits that residual only when the caller names a comparison arm.

**(f) The control-shape band, calibrated on every control arm the lab holds.** Eleven of the 824
recorded dev candidates are control or dose-response arms. Each one's trade count and turnover
against its **nearest sibling by trade ratio**, measured:

> **Corrected 2026-10-19 by the reconciler, twice.**
>
> 1. **`M0005-ALL-R` is struck from this table.** It is not a control arm: its rationale reads
>    *"The same composite with linear rank weights: does conviction in the top names pay"*, which
>    carries no control marker at all. Only its `-R` suffix suggested otherwise, and the suffix is
>    exactly the trap the check must not fall into. `lab/control_shape.py` correctly produces **no
>    finding** for it, and phase 2's test asserts that it produces none.
> 2. **These ratios are nearest-sibling ratios and are superseded.** A control must be measured
>    against *the arm it actually controls*, which is what `control_shape`'s resolution ladder
>    finds; the nearest sibling by trade ratio is a different arm in several rows. The module's
>    resolved-target numbers (phase 2's table) are the ones the plan, the tests and the backtest
>    note quote — e.g. `M0222-RAND1` turnover 4.451x not 2.41x, `M0243-NEAR20-R` 3.013/2.976 not
>    2.16/2.14, `M0248-R` 3.180/3.078 not 3.08/2.88. **Every verdict below is unchanged by the
>    correction**; only the numbers move.

```
control             trades    tov    nearest sibling        trades x   tov x
M0222-RAND1            372   2.34    M0222-TILT1               1.01    2.41
M0222-RAND2            402   4.67    M0222-CORE                1.06    8.86
M0226-RAND1           1239   1.87    M0226-TILT2               1.02    1.56
M0226-RAND2           1682   3.92    M0226-CORE                1.33   14.53
M0230-C50-R             41   0.24    M0230-C50-SWS             0.07    0.14   <-- the known case
M0241-PLACEBO          804   3.20    M0241-SPLIT12             1.37    1.13
M0241-STALE            544   2.97    M0241-FRESH20             1.03    1.01
M0243-NEAR20-R        3872  20.61    M0243-NEAR20-T3           2.16    2.14   <-- a THIRD case
M0244-PLACEBO30       3687  15.05    M0244-FRESH30             1.01    0.98   <-- clean
M0244-STALE30          698   3.57    M0244-HARD30              0.28    0.31   <-- dose-response
M0248-R               4074  21.60    M0248-D75                 3.08    2.88   <-- the known case
```

Four things this table settles, all of which the plan depends on:

1. **Both axes are needed.** `M0226-RAND2` is within 1.33× on trades and 14.5× on turnover; a
   trades-only check misses it entirely.
2. **A third undiscovered case exists**: `M0243-NEAR20-R` trades 2.2-3.4× every sibling. The
   handover knew of two; the check finds three.
3. **Dose-response arms must be excluded.** `M0244-STALE30` and `M0241-STALE` are *supposed* to
   differ in shape — the different date is the dose. Treating them as shape-matched controls
   produces a permanent false alarm on a correct arm.
4. **The band is calibratable.** Clean arms sit at ~1.0 on both axes; every dirty one is at 2.1×
   or worse on at least one. A warn band at 1.25× / 0.8× and a refuse band at 2× / 0.5× separates
   the table exactly, with `M0241-PLACEBO` (1.37 trades, 1.13 turnover) the single warn-only case.
   Re-measured against the *resolved* target the separation is wider still — the clean arms sit at
   0.98-1.02, `M0241-PLACEBO` at 1.372 is the only warn, and the worst clean-side refusal is
   `M0243-NEAR20-R` at 2.976 — so `[0.5, 2.0]` sits inside a gap of 1.372 to 2.976.

**(g) Existing method files cannot be edited to declare a control.** `methods.source_sha` is
written once and trigger-protected; `store.latest_source_sha` demands the file on disk still hashes
to it. Adding a `controls=` keyword to M0230's or M0248's file would break that check for a method
whose trials are already recorded. So the check must identify controls **from recorded rows** —
candidate id and `rationale`, which are consistent across the twelve arms above ("Placebo:",
"Control:", "Within-frame control:", "the dose-response control on the date itself"). A declared
field is available to new methods only.

**(h) `lab run` annotates and does not refuse — this is a written lab decision.** `hardgate.py`
(D15) states the rule for exactly this situation: a run-time gate "would only spend method ids to
say what the first one already says", and the run must complete so the lab can bootstrap. The
control-shape check therefore follows the fold-verdict precedent — loud at `lab run`, refusing at
`lab promote`.

**(i) `lab note`'s duplicate is unremovable by design.** `store.append_analysis` (store.py:964)
reads the current analysis and writes `old + "\n\n" + new`; the `methods_analysis_grows` trigger
permits only growth, so a duplicate is permanent. The fix has to be a refusal *before* the write.

### Assumptions

- The gate premium assumes money out of the market earns nothing, which memory
  (`seer-idle-cash-credit-worth-08-before-2008-only`) establishes is right for 2009-2015 and wrong
  before 2008. The command must carry the caveat per era rather than silently applying one model.
- The fee drag assumes the era's slot size, derived from the owner's funding schedule at the era's
  month offsets. It is a model of the fees, not the fees the run actually paid: `RunStats.costs_usd`
  holds the real figure but is **not** a `trials` column.
- The decomposition is an **attribution under stated assumptions, not an identity**. The terms are
  computed independently and the residual absorbs their error. Saying so in the output is part of
  the deliverable.

---

## Analysis Scope

### Explicitly mentioned files

- `docs/plans/HANDOVER_20261019-the-placebo-is-a-control-not-a-constant.md` — the brief.

### Discovered related files

| File | Why it is in scope |
|---|---|
| `engine/src/seer_engine/commands/lab.py` (2897 ln) | every `lab` subcommand's parser and dispatch; `_note` at 2741 |
| `engine/src/seer_engine/lab/store.py` (2998 ln) | `append_analysis` at 964, the duplicate-note write path |
| `engine/src/seer_engine/lab/walkforward.py` (311 ln) | `measure(curve, start, end, deposits)` — the era slicer |
| `engine/src/seer_engine/backtest/regime.py` (271 ln) | `defunded`, `bucket`, `split` — the de-funding path |
| `engine/src/seer_engine/lab/hardgate.py` (1675 ln) | `trial_deposits` at 587; `check` at 1566; D10/D15 decisions |
| `engine/src/seer_engine/lab/exposure.py` (1167 ln) | `ERAS`/`ERA_LABELS` at 132-138; `arm_of` era-lead math at 667 |
| `engine/src/seer_engine/lab/turnover.py` (740 ln) | `equity_usd`, `slot_usd`, `round_trip`, `price_one` — the fee model |
| `engine/src/seer_engine/sim/costs.py` (292 ln) | `fee_parts`, `FeeParts`, the Gotrade regimes |
| `engine/src/seer_engine/lab/gate_probe.py` (1500 ln) | `gate_off`, `GATE_SYMBOL`, `GATE_N` — generic SPY-200 detection |
| `engine/src/seer_engine/lab/method.py` (235 ln) | `Method`, `Amendment`, `config_text`/`config_digest` |
| `engine/src/seer_engine/backtest/dev.py` | `Candidate` at 180 — what `config_text` does and does not read |
| `engine/src/seer_engine/backtest/book_runner.py` | `_turnover` at 699, `RunStats` at 560 — turnover's definition |
| `engine/src/seer_engine/lab/runner.py` (1265 ln) | `run_method`, `recorded_capital`, `recorded_contributions` |
| `engine/src/seer_engine/lab/real_costs.py` (438 ln) | the `measure`/`format_report`/`journal` report shape |
| `engine/tests/labkit.py` | the synthetic dev market every lab test builds on |
| `engine/tests/test_lab_walkforward.py`, `test_lab_turnover.py`, `test_lab_hardgate.py`, `test_lab_store.py` | the test modules the new work sits beside |

---

## Current Dataflow

### Entry point: `python -m seer_engine lab <subcommand>`

**Location:** `engine/src/seer_engine/commands/lab.py:170` (`add_arguments`), `:645` (`run`)
**Trigger:** CLI. `commands/` modules are discovered automatically; `cli.py` is not edited.
**Dispatch:** `run(args)` switches on `args.lab_command` to one `_<name>(conn, args)` function.
**Exit codes:** 0 ok, 2 `store.LabError` (the lab's rules refused), 1 error.

### The two report shapes already in the codebase

The lab has two kinds of report subcommand, and the new work belongs to the first.

**(A) Pure arithmetic over recorded rows — no research store, no backtest, nothing written.**
`lab regime` (`:2252`), `lab walkforward` (`:2352`), `lab kin` (`:2531`), `lab turnover` (`:2176`).
Each one prints `N (dev trials)` and `test-window looks` before and after, so the "nothing was
recorded" invariant is visible on the terminal rather than merely asserted in a test. `lab regime`
opens the store only for breadth; `lab walkforward` and `lab kin` open nothing.

**(B) Re-run reports — load the store, re-run arms, journal one observation.**
`lab costs` (`:2069`), `lab names` (`:2124`), `lab exposure` (`:2590`), `lab gate` (`:2639`),
`lab survivorship` (`:2480`). Backed by a module exporting `measure` / `format_report` /
`insight_text` / `journal` / `csv_rows`.

### The era-lead chain, as it exists today

```
trials.curve_json  ──json.loads──▶  [(date, float)] monthly curve
trials row         ──hardgate.trial_deposits──▶  {date: unit deposit}
                        │  reads trial_funding.deposits_n, trial_provenance.initial_idr,
                        │  runner.recorded_contributions, regime.bucket
                        ▼
      walkforward.measure(curve, start, end, deposits)
                        │  regime.defunded FIRST, then the date cut (walkforward.py:139)
                        ▼
      Slice(months, total_return, cagr, max_drawdown, mar)
                        │
   the same for REF-SPY-HOLD (trials.n = 1, 1993-02-01..2015-10-16, no deposits)
                        ▼
      era lead = mine.cagr - theirs.cagr
```

**Callers today:** `lab/exposure.py:694` (`arm_of`, per era in `ERAS`), `lab/gate_probe.py:829`,
`lab/survivorship_check.py`, `lab/walkforward.py:evaluate`. Every one of them reaches the same
`walkforward.measure`; `trial_deposits`'s docstring is explicit that this is deliberate — "a second
reconstruction is a second chance to read a deposit as edge".

### The fee chain, as it exists today

```
turnover.equity_usd(months)   ──▶ the owner's funded equity at month m (INITIAL_IDR + m x OWNER_MONTHLY)
turnover.slot_usd(equity, n)  ──▶ one name's slot
turnover.round_trip(slot)     ──▶ (FeeParts buy, FeeParts sell) via sim.costs.fee_parts
                                   trading (0.3%, $0.10 min) + regulatory (0.054%, $0.11 cap)
                                   + sell_extra (0.04%, uncapped) + PPN 11%
```

`trials.turnover` (`book_runner.py:699`) = `sum of fill notionals / mean session equity / years`,
both sides counted. One dollar of turnover is one dollar of notional, so
`fee_drag_per_year ≈ turnover x (round_trip_total / (2 x slot))`.

### The `lab note` write path

```
commands/lab.py:_note (2741)
  └─ store.append_analysis(conn, method_id, Path(args.file).read_text())   [store.py:964]
       ├─ get_method → LabError if absent
       ├─ strips; prepends "### <today>" unless the text already opens with it
       ├─ new = (old + "\n\n" if old else "") + text + "\n"
       └─ UPDATE methods SET analysis = ?, updated = ?
            trigger methods_analysis_grows: refuses any write where the new value does not
            start with the old one. Growth is permitted; removal never is.
  └─ store.update_method(conn, method_id, verdict=...) when --verdict given
```

`_note` prints **nothing** on success, which is the second half of the bug: piped through a filter,
"no output" and "failed" are the same observation, and the exit code belongs to the filter.

### State changes

| Store | What the new work writes |
|---|---|
| `lab/lab.sqlite` | **nothing** from R1 and R2's report paths — they are shape (A). R3 changes a refusal, not a row. |
| `web/data/lab.json` | unchanged, because nothing is journaled. No `lab stage` is needed by this work. |
| Neon Postgres | untouched. |

Note: every `lab` subcommand runs the SQLite migrations on connect, so even a read dirties
`lab/lab.sqlite`'s file bytes (memory: `seer-lab-commands-migrate-lab-sqlite-on-connect`). The
database is never committed from this branch.

---

## Key Data Structures

### `trials` (lab/lab.sqlite) — the decomposition's whole input

```sql
n INTEGER PK, method_id, candidate_id, config_digest, config_text, rules_id, allocator_id,
window CHECK IN ('dev','test'), start, "end", store_fingerprint, git_sha, run_at,
total_return, cagr, max_drawdown, profit_factor, trades INTEGER NOT NULL, sharpe,
exposure, turnover, worst_year, worst_year_return, spy_tr_return, spy_tr_cagr, mar,
failed, eligible, dsr, n_trials_at_run, curve_json TEXT NOT NULL,
UNIQUE (config_digest, window), UNIQUE (candidate_id, window)
```

`trials_no_update` and `trials_no_delete` triggers: append-only, absolutely.
**`exposure` and `turnover` are whole-window scalars.** There is no era-resolved column anywhere.

### `Slice` — `lab/walkforward.py:67`

`(months, total_return, cagr, max_drawdown, mar)` for one date cut of a de-funded curve.

### `ERAS` — `lab/exposure.py:132`

```python
WHOLE = "whole window"
ERAS = (("1996-2002", 1996-01-01, 2002-12-31), ("2003-2008", 2003-01-01, 2008-12-31),
        ("2008", 2008-01-01, 2008-12-31), ("2009-2015", 2009-01-01, 2015-10-16))
ERA_LABELS = (WHOLE,) + tuple(label for label, _s, _e in ERAS)
```

2008 sits deliberately inside 2003-2008. `lab/gate_probe.py:110` imports both from here; the new
module does the same rather than redefining them.

### `Candidate` — `backtest/dev.py:180`

`id, family, rules, allocator, params, rationale, added, owner_inputs`.
**`config_text` reads only `rules`, `allocator.id` and `params`** (`lab/method.py:56`), so a new
defaulted field on `Candidate` does not move any recorded `config_digest`. `rationale` is already
outside the digest and is one line, non-empty, enforced at construction.

### `Method` / `Amendment` — `lab/method.py:118` / `:63`

`all_candidates()` returns originals then each amendment's, in declaration order. No field names a
control arm or what it controls.

### `FeeParts` / `GOTRADE` — `sim/costs.py:72` / `:199`

Three dated regimes. `fee_parts(side, amount, on=None)` → `FeeParts(trading, regulatory, ppn, total)`.

---

## Dependencies

### Configuration / environment

| Name | Meaning here |
|---|---|
| `SEER_LAB_DB` | which `lab.sqlite` the command opens; parallel sessions share state through it |
| `SEER_RESEARCH_STORE` | the dev store; default `research.STORE_DIR` = `engine/.research` |
| `SEER_SV_STORE` | the survivorship-check store; not used by this work |
| `PG_TEST_URL` | Postgres for the DB tests; CI fails if they skip. No new DB test here. |
| `PYTHONPATH=engine/src` | required for any run from a worktree, or pytest silently tests the main checkout |

### External services

None. R1 and R2's report paths open no network, and R1's core opens no research store.

### Research stores present on this machine

`engine/.research` (dev), `engine/.research-sv` (survivorship-check), `engine/.research-test`
(test window). **They are gitignored and therefore absent from the worktree** — any phase that
needs one passes `--store /home/miftah/seer/engine/.research`.

---

## Reference List

Every site the new work reads or changes.

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `add_arguments` subparser block | `commands/lab.py:170-643` | def | `commands` |
| `run` dispatch switch | `commands/lab.py:645` | def | `commands` |
| `_note` | `commands/lab.py:2741` | def | `commands` |
| `_regime` (shape-A precedent) | `commands/lab.py:2252` | call | `commands` |
| `_walkforward` (shape-A precedent) | `commands/lab.py:2352` | call | `commands` |
| `_run` | `commands/lab.py:1546` | def | `commands` |
| `_show` | `commands/lab.py:1492` | def | `commands` |
| `_comparability_warnings` | `commands/lab.py:2217` | def | `commands` |
| `append_analysis` | `lab/store.py:964` | def | `lab` |
| `get_method`, `update_method` | `lab/store.py` | call | `lab` |
| `LabError` | `lab/store.py` | class | `lab` |
| `measure` | `lab/walkforward.py:127` | def | `lab` |
| `Slice` | `lab/walkforward.py:67` | class | `lab` |
| `defunded`, `bucket`, `split` | `backtest/regime.py` | def | `backtest` |
| `BENCH_CANDIDATE` = `REF-SPY-HOLD` | `backtest/regime.py:44` | const | `backtest` |
| `trial_deposits` | `lab/hardgate.py:587` | def | `lab` |
| `mismatches`, `describe` | `lab/hardgate.py:740,785` | def | `lab` |
| `check` (the promotion gate) | `lab/hardgate.py:1566` | def | `lab` |
| `benchmark_n` | `lab/hardgate.py:726` | def | `lab` |
| `ERAS`, `ERA_LABELS`, `WHOLE` | `lab/exposure.py:132-138` | const | `lab` |
| `arm_of` (era-lead precedent) | `lab/exposure.py:667` | def | `lab` |
| `equity_usd`, `slot_usd`, `round_trip` | `lab/turnover.py:262,280,315` | def | `lab` |
| `fee_parts`, `FeeParts`, `GOTRADE` | `sim/costs.py:241,72,199` | def/class | `sim` |
| `GATE_SYMBOL`, `GATE_N`, `gate_off` | `lab/gate_probe.py:126,127,249` | const/def | `lab` |
| `_turnover`, `RunStats` | `backtest/book_runner.py:699,560` | def/class | `backtest` |
| `Candidate` | `backtest/dev.py:180` | class | `backtest` |
| `config_text`, `config_digest` | `lab/method.py:46,52` | def | `lab` |
| `Method.all_candidates` | `lab/method.py:143` | def | `lab` |
| `discover` | `lab/method.py:196` | def | `lab` |
| `recorded_capital`, `recorded_contributions` | `lab/runner.py` | def | `lab` |
| `run_method` | `lab/runner.py` | def | `lab` |
| `fmt_pct`, `fmt_signed_pct`, `fmt_num`, `DASH` | `backtest/metrics.py` | def | `backtest` |
| `smoke_market`, `SMOKE_FIRST` | `tests/labkit.py` | test | `tests` |

---

## Impact Points (files that WILL need changes)

| # | File | Why | Phase |
|---|---|---|---|
| 1 | `engine/src/seer_engine/lab/shortfall.py` | **new** — the decomposition: era gap, gate premium, fee drag, residual split | 1 |
| 2 | `engine/src/seer_engine/commands/lab.py` | the `shortfall` subparser and dispatch entry | 1 |
| 3 | `engine/tests/test_lab_shortfall.py` | **new** — the decomposition's tests, including the calibration table | 1 |
| 4 | `engine/src/seer_engine/lab/control_shape.py` | **new** — control detection, target resolution, the band, the verdict | 2 |
| 5 | `engine/tests/test_lab_control_shape.py` | **new** — pins the eleven-arm calibration table (and that `M0005-ALL-R` yields no finding) | 2 |
| 6 | `engine/src/seer_engine/lab/store.py` | `append_analysis` refuses an identical body | 3 |
| 7 | `engine/src/seer_engine/commands/lab.py` | `_note` prints a confirmation line | 3 |
| 8 | `engine/tests/test_lab_store.py` | the duplicate-note refusal | 3 |
| 9 | `engine/src/seer_engine/commands/lab.py` | the `control` subparser, dispatch, and the `lab run` annotation | 4 |
| 10 | `engine/src/seer_engine/lab/hardgate.py` | (D17): `check` refuses a method with a mis-shaped control | 4 |
| 11 | `engine/tests/test_lab_hardgate.py` | the D17 refusal | 4 |
| 12 | `docs/backtests/2026-10-19-trial-828-shortfall.md` | **new** — the run on trial 828 and what it retires | 4 |

**Three phases touch `engine/src/seer_engine/commands/lab.py`** (impact points 2, 7 and 9). Seer
swarm phases share one worktree and one git index, so concurrent edits to that file would lose
work rather than merely conflict. The plan serialises them through `Depends on` for that reason and
says so explicitly.

**This document describes. The plan files prescribe.**

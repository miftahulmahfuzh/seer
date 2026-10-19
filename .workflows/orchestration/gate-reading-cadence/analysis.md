# Code Analysis: M0260 — the SPY-200 gate's reading cadence

**Type:** Feature Implementation (a new lab method on an existing chassis)
**Date:** 2026-10-19 15:20 WIB
**Session ID:** 20261019-152028-SSYJ
**Plan:** `docs/plans/GATE_READING_CADENCE_PLAN.md` (4 phases)
**Worktree:** `/home/miftah/.worktrees/seer/gate-reading-cadence` — branch `feature/gate-reading-cadence`, base `origin/main` @ `5210f35`

---

## User Input

### Original User Request

> M0260 — sweep the SPY-200 gate's reading cadence from weekly to yearly on M0072-Z2-RAWRANK's book, as a dose-response ladder in the checking interval.
>
> Why this is worth a method id: M0258 (just run, trials 829-834) measured the gate read MONTHLY beating the same gate read WEEKLY by +7.01 pts/yr money-weighted and 11.69 points of worst fall, on the same book with nothing else moving — 12.33%/yr and a 23.80% fall against 5.32%/yr and a 35.49% fall. That is larger than the price band is worth at any cadence, and larger than the constant 3.6 pts/yr gate premium. Every lab book inherits its gate cadence from however often it happens to re-pick stocks, and nobody ever chose it. The question is where it turns: a gate read yearly is barely a gate at all, and gating is worth 3.6 pts/yr after 2009, so a best speed must exist between weekly and yearly.
>
> Read first: docs/plans/HANDOVER_20261019-the-gate-price-band.md, then M0258's six recorded trials and its analysis.
>
> Cautions the plan must carry:
> - The walk-forward folds pick each fold's variant by MAR, so they favour whichever arm trades least. Read the folds arm by arm.
> - The cadence axis is only clean on a book whose event hold is counted in SESSIONS rather than calendar months. M0072 qualifies; M0197 does not, because its chooser keys its re-pick on data_date.month.
> - Check sim.rules.PRESETS before assuming any arm is promotable: there is no weekly fractional Gotrade preset, and probably no quarterly or yearly one either. If the winning cadence has no preset, say so in the plan rather than minting one mid-run.
> - Quote trial_funding.mwr (what lab show prints as "your money earned") and never total_return or cagr: these books are funded with the owner's monthly top-up and the curve-shape columns count his deposits as gains.
> - Separating cadence from re-pick frequency is the hard part of this design. Changing the rule set's cadence moves BOTH how often the gate is read and how often the book re-picks. If those cannot be separated on this chassis, say so explicitly and plan the confound in rather than papering over it — that is itself the finding.
> - Do not spend a test-window look. Four are spent and all four failed.

### User-Provided Context

`docs/plans/HANDOVER_20261019-the-gate-price-band.md` (read in full), M0258's six recorded
trials (`lab show M0258`, read in full) and its recorded analysis.

### User-Provided Files

None marked with `@`. The files named in prose were read: the handover, and through it
`engine/src/seer_engine/lab/methods/m0258_gate_price_band.py`,
`m0072_standardised_earnings_jump.py`, `m0063_earnings_day_jump.py`,
`m0101_calm_raisers_banded_switch.py`, `engine/src/seer_engine/sim/rules.py`,
`engine/src/seer_engine/backtest/book_runner.py`,
`engine/src/seer_engine/strategies/f_factor.py`, `engine/tests/test_lab_m0258_band.py`.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Sweep the SPY-200 gate's reading cadence from weekly to yearly on M0072-Z2-RAWRANK's book, under method id M0260, as a dose-response ladder in the checking interval, and find where it turns |
| R2 | Read the walk-forward folds arm by arm, because the folds pick each fold's variant by MAR and so favour whichever arm trades least |
| R3 | Run the axis only on a book whose event hold is counted in sessions, not calendar months — M0072 qualifies, M0197 does not |
| R4 | Check `sim.rules.PRESETS` before calling any arm promotable, and say in the plan when a winning cadence has no preset rather than minting one mid-run |
| R5 | Quote `trial_funding.mwr` throughout, never `total_return` or `cagr` |
| R6 | Separate the gate's reading cadence from the book's re-pick frequency — or state explicitly that they cannot be separated on this chassis and plan the confound in |
| R7 | Spend no test-window look |

---

## Detailed Requirements Understanding

**Problem statement.** M0258 measured one paired difference it was not looking for: the same book,
the same bare SPY-200 gate, nothing moving but the rule set's cadence, earned **12.33%/yr** of the
owner's own money read monthly against **5.32%/yr** read weekly, and fell **23.80%** against
**35.49%**. The lab has never chosen a gate cadence; every book inherits it from whatever rule set
it happens to run on. M0260 is bought to find where that axis turns.

**What "done" looks like.** One pre-registered method, id M0260, recorded on the dev window as a
dose-response ladder in the gate's checking interval; a recorded verdict and a plain-language
analysis quoting money-weighted returns; a handover; and an explicit, measured statement of how far
the cadence axis can be separated from the re-pick axis on this chassis.

**Key considerations, and what the code says about each.**

1. **The confound is real, and it is one-sided.** The allocator is called *only* on decision
   sessions (`book_runner.run_book`, line 393-403), with `data_date = prev_session(S)`. The gate is
   read inside that call, at `data_date`. So "how often the gate is read" and "how often the book
   re-picks" are literally the same event as the chassis stands. But the asymmetry matters: a book
   can be made to read the gate **more slowly** than it re-picks without touching the rule set —
   hold the reading at an earlier anchor — while it cannot be made to read it **faster**, because a
   reading the book never acts on changes nothing. The ladder above monthly is therefore clean and
   promotable; the rung below monthly is inseparably confounded. §"The confound, measured" below.
2. **The confound can be decomposed even where it cannot be separated.** A third arm — weekly
   re-pick, gate anchored to the month — splits M0258's +7.01 pts into a re-pick-frequency term and
   a gate-cadence term that sum to it exactly.
3. **There is no quarterly or yearly rule set, and there never can be one without a schema move.**
   `sim.rules.Cadence` is `Literal["daily", "weekly", "monthly"]`. The slow rungs cannot be
   expressed as a rule set at all; they must live in the allocator's params. This is why they stay
   promotable.
4. **`WEEKLY_HOLD_FRAC_GOTRADE` is not in `PRESETS`.** Both weekly arms are diagnostic forever.
5. **Funded books.** Every headline is `trial_funding.mwr`; `total_return` and `cagr` count the
   owner's deposits as gains.
6. **No test-window look.** `lab test` is never invoked by this plan, under any outcome.

---

## Analysis Scope

### Explicitly mentioned files

- `docs/plans/HANDOVER_20261019-the-gate-price-band.md`

### Discovered related files

- `engine/src/seer_engine/lab/methods/m0258_gate_price_band.py` — the overlay template this
  method copies (named by the handover)
- `engine/src/seer_engine/lab/methods/m0072_standardised_earnings_jump.py` — the host book
  (`ZJUMP`, `ZParams`, `ZPrepared`, `JUMP20`), imported by m0258
- `engine/src/seer_engine/lab/methods/m0063_earnings_day_jump.py` — defines
  `WEEKLY_HOLD_FRAC_GOTRADE` (m0063.py:64), imported by m0258
- `engine/src/seer_engine/sim/rules.py` — `TradeRules`, `Cadence`, `_first_of`,
  `is_rank_session`, `PRESETS`
- `engine/src/seer_engine/backtest/book_runner.py` — where `data_date` comes from
- `engine/src/seer_engine/strategies/f_factor.py` — `trend_on`, the gate itself
- `engine/src/seer_engine/strategies/base.py` — `History` (`dates`, `index_of`, `upto`)
- `engine/src/seer_engine/dates.py` — the NYSE calendar (`sessions`, `next_session`, `prev_session`)
- `engine/src/seer_engine/lab/method.py` — `Method`, `Candidate`, `config_text`, `config_digest`
- `engine/src/seer_engine/lab/runner.py` — `lab run`: how an `idea` row becomes a method
- `engine/src/seer_engine/lab/hardgate.py` — (F), (K), D14, D17
- `engine/tests/test_lab_m0258_band.py` — the dedicated-test-module pattern
- `engine/tests/allocatorkit.py` — `assert_p4_identity`, `assert_no_lookahead`
- `docs/backtests/2026-10-19-gate-band-cadence.py` — the feasibility-grid precedent

---

## Current Dataflow

### Entry point: `lab run M0260`

**Location:** `engine/src/seer_engine/commands/lab.py:231` → `lab/runner.py`
**Trigger:** CLI, after the method file is committed (the commit is the pre-registration).
**Validation:** the file's sha must be committed and clean; its config digests must not already
have run.
**Row handling:** `runner.py:756-762` — when the `methods` row is still `idea`, the runner
**overwrites name, family, source_kind and hypothesis from the method file** and then moves the
row `idea -> registered`. M0260 already exists as an `idea` row (queued by M0258's run), so the
method file — not the queued row — is authoritative for every field.

### Processing chain: how the gate actually gets read

1. **`book_runner.run_book`** — `engine/src/seer_engine/backtest/book_runner.py:368, 393-403`
   - `data_date = dates.prev_session(start)` initially, then `data_date = session` at the foot of
     each loop iteration (line 454). So at session `S`, `data_date` is the **previous session**.
   - `rank = is_rank_session(rules, session)`; the allocator is called **only** when
     `rank or (last_rank is not None and is_resize_session(...))`.
   - It is called as `allocator.targets_prepared(prepared, members, data_date, mine, params)`.
   - **Consequence:** the allocator sees one `data_date` per decision session and nothing else.
     There is no seam at which it could be handed a faster clock.

2. **`sim.rules.is_rank_session` / `_first_of`** — `engine/src/seer_engine/sim/rules.py:368-397`
   - `monthly`: `(session.year, session.month) != (prev_session(session).year, .month)` — the
     **first NYSE session of the calendar month**.
   - `weekly`: the first NYSE session of the ISO (year, week).
   - **Consequence, and the fact the whole design turns on:** for a monthly rule set,
     `data_date = prev_session(first session of month M)` = **the last NYSE session of month M-1**.
     A monthly book's `data_date` is *always* a calendar month end. A weekly book's is always a
     week end and only occasionally a month end.

3. **`f_factor.trend_on(history, data_date, params)`** — `strategies/f_factor.py:234-253`
   - `symbol, n = params.trend` (`("SPY", 200)` for this book); `i = h.index_of(data_date)`;
     returns `False` when the symbol has no bar dated exactly `data_date` or `i + 1 < n`;
     otherwise `close[i] > SMA200`.
   - Reads only bars dated `<= data_date`.

4. **`m0258.BandedGateAllocator`** — the overlay template
   - `lookback`, `symbols`, `holds`, `uses_members`, `prepare` all delegate to `ZJUMP`.
   - `_on(history, data_date, p)` is the single replaced line.
   - `targets` / `targets_prepared` call `ZJUMP._targets(...)` **directly**, with the host's own
     `ZParams`, so the book is provably unchanged and only the gate differs. The private call is
     justified in the file: `m0072.py` is frozen against its recorded `source_sha`.

### Data persistence

**Database:** `lab/lab.sqlite` (append-only, trigger-enforced). `lab run` writes one `trials` row
per candidate plus a `trial_funding` row per trial, and moves `methods.status` to `dev-eligible`
or `rejected` in the same transaction. `lab stage` regenerates `web/data/lab.json` and git-adds it
with the database — **targeting the main checkout `/home/miftah/seer`, not the worktree**.

### Exit points

`lab show`, `lab walkforward`, `lab control`, `lab costs`, `lab note`, `lab insight`, `lab stage`;
and `web/data/lab.json` → `seertrade.site/sera`.

---

## Key Data Structures

### `TradeRules` — `sim/rules.py:104`

```
Cadence = Literal["daily", "weekly", "monthly"]
```

**There is no `"quarterly"` and no `"yearly"`.** Adding one would move `_CADENCE_ORDER`,
`_first_of`, `is_rank_session`, every `TradeRules` digest's canonical text and the web mirror in
`web/.../cadence.ts`. This is the single most important structural fact for the design: the slow
rungs of the ladder **cannot** be a rule set, so they must be allocator params — which is exactly
what keeps them promotable.

### `PRESETS` — `sim/rules.py:308-328`

Contains `MONTHLY_HOLD_FRAC_GOTRADE` (rules.py:261). **Does not contain**
`WEEKLY_HOLD_FRAC_GOTRADE`, which is defined in `m0063_earnings_day_jump.py:64` under its own
comment: *"No preset of this id exists yet: it runs on dev, and `promote` would need one (a
feature-wish if it wins)."*

| arm family | rule set | in `PRESETS`? | promotable? |
|---|---|---|---|
| every monthly arm | `monthly-hold-frac-gotrade` | **yes** | yes |
| every weekly arm | `weekly-hold-frac-gotrade` | **no** | **never** |

### `History` — `strategies/base.py:34`

`dates` is a `datetime64[D]` numpy array, strictly ascending; `index_of(d)`, `upto(d)`,
`last_date()`. Enough to find a month-end anchor without any calendar call except one.

### `Method` / `Candidate` / `config_text` — `lab/method.py:43-51, 132-142`

`config_text` is `rules`, `allocator.id` and `params` only. **A new params field that `as_dict`
does not render makes two arms share one digest, and the second is refused as already run.**

---

## The confound, measured

This is the part of the request that has no code answer until it is written down, so it is written
down here in full.

### Why the two axes are the same event today

The allocator is invoked once per decision session with that session's `data_date` and reads the
gate at `data_date`. "How often the gate is read" is therefore *defined* by the rule set's
`cadence`, which is also what sets how often the book re-picks. M0258's +7.01 pts/yr is the sum of
both effects and names neither.

### Direction A — a gate SLOWER than the re-pick: separable, and promotable

Nothing stops the allocator from evaluating the gate at a date **earlier** than `data_date`. Define

```
month_index(d) = (d.year - 1970) * 12 + (d.month - 1)

anchor(h, data_date, k) = the newest bar a of h with a <= data_date such that
                            (i)  a is the last session of its calendar month, and
                            (ii) month_index(a) % k == k - 1
                          falling back to data_date when no such bar is on hand
```

Phase `k - 1` makes the grid calendar-natural: `k=1` every month end, `k=2` Feb/Apr/…/Dec,
`k=3` Mar/Jun/Sep/Dec (calendar quarters), `k=6` Jun/Dec, `k=12` December only.

Condition (i) is decidable point-in-time: for an interior bar `j` it is
`month(dates[j]) != month(dates[j+1])`; for the newest bar on hand it is the calendar question
`dates.next_session(d).month != d.month`, which reads the published NYSE calendar and no price.
**A calendar read inside a lab allocator is established practice** — `m0052_turn_of_month_tilt.py`
(lines 96, 111-114, 180), `m0120_calendar_clock.py`, `m0024`, `m0051`, `m0079`, `m0085`, `m0086`,
`m0204` and `m0020` all do it, and `allocatorkit.assert_no_lookahead` perturbs *bars*, not the
calendar.

Three consequences, all of which the plan depends on:

- **The book still re-picks monthly.** `TradeRules` is untouched, so the rule set stays
  `monthly-hold-frac-gotrade`, which is in `PRESETS`. **Every slow rung is promotable.**
- **On a monthly book, `k=1` resolves to `data_date` itself**, because a monthly book's `data_date`
  is always a calendar month end (§Current Dataflow, step 2). So the anchored `k=1` arm *is* the
  native arm, and the ladder's fastest rung costs no trial — it is an identity to assert in the
  test module, not a row to record.
- The anchor is never later than `data_date`, so it is strictly safer than the native reading on
  look-ahead.

### Direction B — a gate FASTER than the re-pick: not separable, by construction

A monthly book cannot act on a gate reading taken between its rank sessions; a reading it never
acts on changes no target and no trade. Making the book act weekly *is* changing the rule set's
cadence, which also re-picks weekly. **On this chassis the sub-monthly rung of the ladder is
inseparably confounded, and that is a property of the simulator, not an oversight in the design.**

### What can be done instead: decompose it exactly

Three arms, with `A - B` being precisely the +7.01 pts/yr M0258 measured:

| | re-pick | gate read | recorded twin |
|---|---|---|---|
| **A** | monthly | monthly (native) | `M0258-M-B0` = `M0072-Z2-RAWRANK`, 12.33%/yr, 23.80% |
| **C** | **weekly** | **monthly** (anchored, `k=1`) | *new — this is the decomposition arm* |
| **B** | weekly | weekly (native) | `M0258-W-B0`, 5.32%/yr, 35.49% |

```
(A - B)  =  (A - C)             +  (C - B)
   total      re-pick frequency     gate reading cadence
             (gate held fixed)      (re-pick held fixed)
```

And the first bracket is clean for a reason worth stating: at a weekly rank session in month `M`,
arm C's anchor is the newest month end on or before its `data_date`, which is the **same month-end
session** arm A read at its own rank session that month. Arm C literally reuses arm A's gate
reading. So `A - C` moves re-pick frequency and nothing else.

### What this does not reach

The decomposition is exact at the weekly/monthly pair only. Nothing here makes a *sub-weekly* gate
separable, and nothing makes a monthly book read a gate faster than monthly. Both are stated as
limits in the method file rather than worked around.

---

## Dependencies

### Configuration / environment

- `SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite` — the shared, append-only lab. **A worktree copy
  must never be written**, and even a read migrates the file on connect.
- `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research` — the dev store. **Never rebuild it.**
  It does not exist inside a worktree.
- `PY=/home/miftah/seer/engine/.venv/bin/python` — the worktree has no venv.
- `PYTHONPATH=<worktree>/engine/src` — without it pytest silently tests the main checkout.
- Postgres for the DB tests: `docker start seer-pg`,
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres`.
- One core: `pytest -n0`; never override `addopts`.

### External services

None. Nothing in this plan touches the network, Neon, Vercel or the EODHD cache.

### Hard-gate state (read 2026-10-19, before any run)

- The only `test-failed` methods in the lab are **M0002** (`stock-momentum-risk-managed`),
  **M0021** and **M0029** (`stock-multi-factor-blend`) and **M0022** (`stock-residual-momentum`).
- `market-trend-switch` holds M0084, M0113, M0136, M0245 (all `rejected`) and M0234, M0255, M0259,
  M0260 (ideas). **No test-failed member.**
- M0260's ancestry is M0258 → M0072 → M0063, all `stock-event-drift`, none test-failed.
- So **either family choice is kin-clean on (D12)**; the choice is editorial, not a gate decision.
- **(D17)** refuses only *drawn* control arms. A dose-response ladder whose zero rung is the
  control has none — `lab control M0258` returned four `dose-response` rows, no ratio, no refuse.
  M0260 has the same shape.
- **(D14)** compares a `test-failed` method's tested variant against each dev variant at
  `KIN_CORRELATION`. M0258 came back kin-clean on the identical book; M0260's slow-gate arms hold
  stocks a *larger* fraction of the time, which can only move that correlation, so it is a live
  risk rather than a settled one.

### Lab state

| | |
|---|---|
| dev trials | 830 |
| test-window looks used | **4 — and this plan spends none** |
| N the luck gate judges at (policy: methods) | 163 |
| M0260 | exists as an `idea` row, family `market-trend-switch`, parent M0258 |
| next free id | M0261 (so M0260 is this method's id, already reserved) |

---

## Reference List

Every site the new method touches or reads. Nothing existing is edited: this is an additive
method, and the one judgement call below is about *not* editing.

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `ZJUMP`, `ZParams`, `ZPrepared`, `JUMP20` | `lab/methods/m0072_standardised_earnings_jump.py:…` | import (read-only) | `lab.methods` |
| `ZJUMP._targets` | `m0072_standardised_earnings_jump.py` | private call, precedent in m0258 | `lab.methods` |
| `WEEKLY_HOLD_FRAC_GOTRADE` | `m0063_earnings_day_jump.py:64` | import | `lab.methods` |
| `MONTHLY_HOLD_FRAC_GOTRADE` | `sim/rules.py:261` | import | `sim` |
| `PRESETS` | `sim/rules.py:308` | read — promotability check | `sim` |
| `Cadence` | `sim/rules.py:56` | read — no quarterly/yearly exists | `sim` |
| `_first_of`, `is_rank_session` | `sim/rules.py:368, 390` | read — fixes what `data_date` is | `sim` |
| `data_date = prev_session(...)` | `backtest/book_runner.py:368, 454` | read | `backtest` |
| `trend_on` | `strategies/f_factor.py:234` | call, at the anchor | `strategies` |
| `factor_rows` | `strategies/f_factor.py` | call | `strategies` |
| `dates.next_session` | `dates.py:86` | call — month-end test | top level |
| `History.dates` / `index_of` | `strategies/base.py:38, 86` | read | `strategies` |
| `Candidate`, `Method`, `config_digest` | `lab/method.py:43-51, 132` | construct | `lab` |
| `BandedGateAllocator` | `m0258_gate_price_band.py` | **template only — not imported, not edited** | `lab.methods` |
| `test_lab_m0258_band.py` | `engine/tests/` | pattern only — not edited | tests |
| `labkit.smoke_market`, `MEMBER_STOCKS`, `SMOKE_FIRST` | `engine/tests/labkit.py` | import in the new test | tests |
| `allocatorkit` | `engine/tests/allocatorkit.py` | driven by `test_lab_methods` automatically | tests |
| `docs/backtests/2026-10-19-gate-band-cadence.py` | `docs/backtests/` | precedent for the prior grid | docs |

---

## Impact Points (files that WILL need changes)

New files only. **No existing source file is edited by this plan** — the method-file discovery in
`lab/methods/` is automatic, and `commands/cli.py` discovers subcommands automatically.

1. `docs/backtests/2026-10-19-gate-reading-cadence.py` — **new.** The SPY-alone cadence ladder and
   the anchor probe on the real dev store. The prior the method file must quote, measured before
   any pre-registration prose exists. *(Phase 1)*
2. `docs/backtests/2026-10-19-gate-reading-cadence.md` — **new.** Its output, committed. *(Phase 1)*
3. `engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py` — **new.** The method:
   `CadenceParams`, `SlowGateAllocator` (id `M0260`), six candidates, `METHOD`. `lab/method.py:40`
   caps a method at `MAX_VARIANTS = 6`, so the `k = 2` rung is deferred to an `Amendment`,
   which costs no method id. The plan index's Appendix A is binding. *(Phase 2)*
4. `engine/tests/test_lab_m0260_cadence.py` — **new.** The claims `allocatorkit` cannot check:
   the anchor grid, the `k=1`-is-native identity on a monthly book, the weekly/monthly arm reusing
   the monthly arm's own reading, params round-trip and digest separation, and that every rung
   actually changes the gate somewhere on the tape. *(Phase 2)*
5. `lab/lab.sqlite` + `web/data/lab.json` — **appended to**, in the **main checkout**, by
   `lab run` / `lab note` / `lab insight` / `lab stage`. *(Phase 3)*
6. `docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md` — **new.** *(Phase 4)*
7. `.workflows/todos.md` — **appended to.** *(Phase 4)*

**This document describes. The plan files prescribe.**

# Code Analysis: the drawdown bar — one number doing two jobs

**Type:** Feature Update
**Date:** 2026-10-14 09:52:18 +07
**Session ID:** 20261014-095218-B7QD
**Plan:** `docs/plans/SPLIT_SCREEN_FROM_BAR_PLAN.md` (2 phases)
**Worktree:** `/home/miftah/.worktrees/seer/split-screen-from-bar`, branch `feature/split-screen-from-bar` (base `origin/main` @ `49287bb`)

---

## User Input

### Original User Request

> "i agree with you. this is what i am afraid of. beating SPY is so hard already, yet we still
> impose these strict constraints . you know what, let's do your suggestion, and in fact, raise my
> risk appetite more to 25%"

"Your suggestion" is the decoupling proposal the owner is agreeing to: keep the figure as the
REAL-MONEY bar applied at promotion, and loosen it on the DEV SCREEN, whose job is to surface
candidates worth studying — so a method can be found, measured and understood while still being
refused real money. He then went further and raised the real-money bar itself to 25%.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Raise the real-money drawdown bar from 20% to 25% (§1 go-live condition 4, the promote gate, the leaderboard) |
| R2 | Split the lab's dev-eligibility screen off from that bar, so a method can be studied without being fundable |
| R3 | Record it as a dated owner revision in the design doc, the way §11 and §13 record their predecessors |
| R4 | Keep engine and web agreeing — the bar reaches the web twice, as a TS constant and through `lab.json` |

---

## Detailed Requirements Understanding

**Problem.** `MAX_DRAWDOWN` is one constant doing two unrelated jobs. It decides what the owner
may hold with real money (§1 condition 4, a statement about his risk appetite) **and** what the
lab will even look at (`eligible`, a statement about research budget). Measured against the 399
recorded dev trials, the second job is the binding constraint on the whole research programme.

**Success criteria.** Two constants exist. The real-money one reads 0.25 and is what
`owner_failures`, `hardgate.check`, the go-live checklist and the leaderboard read. The screen is
a separate, looser number read **only** by the dev-eligibility path. A dated revision records the
decision. Engine and web agree.

**Key consideration — recorded rows move verdict, and that is correct.** `eligible` and `failed`
are re-derived from recorded columns against live constants (`store.py:1418-1420`), so changing a
constant legitimately changes verdicts without editing a row. The recorded `failed` *text* of the
30 rows judged at 15% keeps its recorded wording; that is the existing contract and this change
does not touch it.

**Assumption stated.** The screen's value is a judgement, not a derivation. 0.50 is proposed
because SPY itself fell 56.5%; an implementer may argue another number from measurement, but must
not collapse the two constants back into one, which would undo R2.

---

## Analysis Scope

### Explicitly Mentioned Files

- `engine/src/seer_engine/backtest/metrics.py` — the single definition
- `engine/src/seer_engine/backtest/tuning.py` — the re-export every caller reads
- `engine/src/seer_engine/lab/store.py` — both the screen and the go-live check
- `docs/plans/2026-10-03-seer-design.md` — §1 and the revision series
- `web/lib/golive.ts`, `web/lib/golive.test.ts` — the mirror

### Discovered Related Files

- `engine/src/seer_engine/lab/hardgate.py:1569` — the (D16) survivorship rule reads the bar
- `engine/src/seer_engine/lab/npolicy.py:156` — `dev_method_count`, which decides whether the screen touches N
- `engine/src/seer_engine/backtest/report.py`, `b_report.py`, `b_walkforward.py` — prose quoting the bar

---

## Current Dataflow

### Entry point: `metrics.MAX_DRAWDOWN`

**Location:** `engine/src/seer_engine/backtest/metrics.py:55`, currently `0.20`.
Its docstring states it is the single definition in Python and that `tuning.MAX_DRAWDOWN`
re-exports it, so every caller resolves to one float. It lives in `metrics` rather than `tuning`
only because `tuning` imports `metrics` and the dependency cannot run the other way.

### The two jobs, already at separate call sites

**CORRECTED 2026-10-14 — the first draft of this section named the two functions the wrong way
round, and the error mattered.** Measured: `store.py:1463` is inside **`owner_failures`** (def at
`:1411`) and `store.py:1801` is inside **`_blocking`** (def at `:1769`).

| Location | Function | What it decides |
|---|---|---|
| `store.py:1463` | `owner_failures` | the owner conditions — and `eligible` is `not owner_failures(...)` |
| `store.py:1801` | `_blocking` | raises `LabError` for a trial that cannot be reasoned about |

**So the two jobs were never at separate call sites.** `owner_failures` IS both jobs at once:
it is the §1 condition check *and* the thing that produces `eligible`. That is precisely why one
constant was doing two jobs — not an accident of sharing a constant, but one function answering
two questions. R2 is therefore a four-site change, not a one-line one:
`dev.py:96` (the failure label), `dev.py:440` (`make_row`, which births `eligible` on new trials),
`store.py:1463` and `store.py:1801` (or `lab reevaluate` crashes on 7 recorded trials).

### Other readers of the bar — all legitimately the real-money bar

- `store.py:1904` — the gate's explanatory sentence
- `store.py:2894` — `"maxDrawdown": tuning.MAX_DRAWDOWN` written into `web/data/lab.json`
- `hardgate.py:1569` — the (D16) rule refusing a variant the fuller history sinks
- `metrics.py:506` + `MAX_DRAWDOWN_LABEL` — the go-live checklist and its label
- `report.py:251,257,294`, `b_report.py:495,499`, `b_walkforward.py:470` — prose

### How the bar reaches the web — twice

1. `web/lib/golive.ts:21` — `export const MAX_DRAWDOWN = 0.2;` and `:41` the label.
2. `web/data/lab.json`'s `gate.maxDrawdown`, written by `store.snapshot`.

`web/lib/golive.test.ts:10` pins the two together (`expect(MAX_DRAWDOWN).toBe(lab.gate.maxDrawdown)`)
and `:14` pins the label string `'Max drawdown ≤ 20%'`. **So the TS constant, the committed
`lab.json` and the engine must move in one commit**, or that test fails.

Note `test_sean_mirrors.py` does **not** cover this constant (it covers resize band, target resize
band, owner monthly, USD/IDR). The `0.20` in `web/lib/cadence.ts` is `TARGET_RESIZE_BAND` and is
unrelated.

### State changes

None in the database. No row is written or edited; `eligible` and `failed` are derived at read
time. `lab stage` regenerates `web/data/lab.json` from the committed `lab.sqlite`, and both are
committed together.

---

## Measurements

Read-only on `lab/lab.sqlite` at `main`, hash `2c8c9669…` unchanged throughout.

### M1 — the screen is the binding constraint

| | fall ≤ 20% | fall > 20% |
|---|---|---|
| **beats SPY TR** | 69 | **188** |
| loses to SPY TR | 24 | 118 |

**257 of 399 dev trials beat SPY TR, and the bar rejects 188 of them — 73%.**

### M2 — what the benchmark itself does

SPY's max drawdown over the dev window is **56.5%** (trough 2009-03-09) at **7.86%/yr**. The lab
requires its strategies to fall less than a third as far as the benchmark they must beat.

### M3 — what each screen value admits, ON THE DRAWDOWN CONDITION ALONE

**Read the heading carefully — this is not an eligibility count**, and conflating the two would
put a wrong *kind* of number into a permanent owner record. These are trials that clear the
drawdown condition by itself; dev-eligibility additionally requires beats-SPY, profit factor,
trades, owner-inputs **and** the luck test.

| screen | clear the drawdown condition | of which beat SPY | distinct methods |
|---|---|---|---|
| 0.20 (today) | 93 | 69 | 30 |
| 0.25 | 196 | 160 | 53 |
| 0.40 | 303 | 224 | 63 |
| **0.50** | **319** | **233** | **64** |
| 0.5665 (SPY's own) | 338 | 242 | 65 |

### M3b — what each screen value admits as DEV-ELIGIBLE (all conditions, the live gate)

The recorded `eligible` column today reads **22 trials across 11 methods**. Re-derived against the
live constants at `N = 81` methods, the screen moves eligibility roughly:

| screen | dev-eligible trials | distinct methods |
|---|---|---|
| 0.20 (today) | ~26 | ~16 |
| 0.25 | ~60 | ~30 |
| **0.50** | **~67** | **~32** |

**This is the number §18 must quote**, and phase 1 re-derives it rather than trusting these.
The headline in M1 is unaffected — 188 of the 257 trials that beat SPY are rejected *by the
drawdown condition*, which is a statement about that condition and remains exactly true.

### M4 — the screen cannot inflate N

`npolicy.dev_method_count` (`npolicy.py:156`) counts distinct methods with **any** dev trial,
regardless of eligibility. Loosening the screen therefore cannot move N or any DSR. This removes
the one substantive objection to R2.

### M5 — blast radius, measured by making the change and running the suite

**40 tests fail.** Not all cosmetic:

- `test_lab_gate_policy.py` (9) — the hardest. Several encode **historical** claims about the
  2026-10-07 15%→20% move, guarded by their own premise assertions (`assert tuning.MAX_DRAWDOWN
  == 0.20`, `test_the_two_moved_bars_unblock_exactly_m0022_and_m0020`). They must be re-expressed
  so the historical claim stays true and testable.
- `test_backtest_*` (~15) — prose and thresholds: gate sentences quoting "max drawdown ≤ 20%",
  `test_eligibility_boundaries`, `test_the_drawdown_label_follows_the_bar`.
- `test_lab_*` (the rest) — `test_lab_snapshot` (needs `lab stage`), `test_lab_prereg`,
  `test_lab_status`, `test_lab_luck`, `test_lab_test_window`, and the (D16) hardgate test.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `MAX_DRAWDOWN` | `backtest/metrics.py:55` | def | `engine/backtest` |
| `MAX_DRAWDOWN_LABEL` | `backtest/metrics.py:508` | def | `engine/backtest` |
| `MAX_DRAWDOWN` | `backtest/tuning.py:41` | re-export | `engine/backtest` |
| checklist item 4 | `backtest/metrics.py:506` | call | `engine/backtest` |
| **the screen** | `lab/store.py:1463` | call — **changes** | `engine/lab` |
| its docstring | `lab/store.py:1423` | doc — **changes** | `engine/lab` |
| `owner_failures` | `lab/store.py:1801-1802` | call — stays | `engine/lab` |
| gate wording | `lab/store.py:1904` | call — stays | `engine/lab` |
| `snapshot` | `lab/store.py:2894` | call — stays | `engine/lab` |
| (D16) rule | `lab/hardgate.py:1569` | call — stays | `engine/lab` |
| `dev_method_count` | `lab/npolicy.py:156` | def — proves M4 | `engine/lab` |
| prose | `backtest/report.py:251,257,294` | doc | `engine/backtest` |
| prose | `backtest/b_report.py:495,499` | doc | `engine/backtest` |
| prose | `backtest/b_walkforward.py:470` | doc | `engine/backtest` |
| `MAX_DRAWDOWN` | `web/lib/golive.ts:21` | mirror | `web` |
| `MAX_DRAWDOWN_LABEL` | `web/lib/golive.ts:41` | mirror | `web` |
| the pin | `web/lib/golive.test.ts:10,14` | test | `web` |
| `gate.maxDrawdown` | `web/data/lab.json` | data | `web` |
| §1 condition 4 | `docs/plans/2026-10-03-seer-design.md:20` | doc | `docs` |
| revision series | same, `## 11.`, `## 13.`, `## 16.`, `## 17.` | doc | `docs` |

---

## Impact Points

1. `backtest/metrics.py` — `MAX_DRAWDOWN` 0.20 → 0.25; new `DEV_MAX_DRAWDOWN`. Phase 1.
2. `backtest/tuning.py` — re-export the new constant. Phase 1.
3. `lab/store.py:1463` + its docstring at `:1423` — the screen reads the new constant. Phase 1.
4. ~40 engine tests. Phase 1.
5. `web/lib/golive.ts` + `golive.test.ts`, `web/data/lab.json`, `lab/lab.sqlite`. Phase 1 — they
   must move in the same commit as the engine or `golive.test.ts` fails.
6. `docs/plans/2026-10-03-seer-design.md` — a new `## 18.` revision. Phase 2.

**This document describes. The plan files prescribe.**

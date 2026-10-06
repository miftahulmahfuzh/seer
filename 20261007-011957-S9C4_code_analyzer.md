# Code Analysis: nightly paper trading for split-cadence rules (monthly pick, weekly resize)

**Type:** Feature Implementation
**Date:** 2026-10-07 01:19 (WIB)
**Session ID:** 20261007-011957-S9C4
**Plan:** `PAPER_SPLIT_CADENCE_PLAN.md` (3 phases)
**Worktree:** `/home/miftah/.worktrees/seer/paper-split-cadence` on `feature/paper-split-cadence` (base `origin/main` @ `dffac31`)

---

## User Input

### Original User Request

```
/analyze @docs/handover/2026-10-07-paper-split-cadence.md
```

The handover file is the specification. Its decisions (§4) and open questions (§5) are quoted here
verbatim because they are the requirements:

> ## 4. The work (decisions already made)
>
> 1. **`decide_book` accepts split-cadence rules.** It takes the last rank basket (pre-idle, in
>    current units) and the book's marks, and on a resize-only session returns exactly what
>    `run_book` would execute: `_with_idle(_rescaled(...))`. On a rank session nothing changes. The
>    function stays pure (it lives under `paper/`, purity-tested).
> 2. **The last rank basket is persisted, not recomputed.** Recomputing from history would be a
>    second source of truth. Decide in the analysis between (a) reading it back from `book_targets`
>    of the last rank session (pre-idle, split-adjusted to now), or (b) a new column/table. Prefer
>    (a) if it is exact; record why if not.
> 3. **Replay agrees.** `paper_check` must stay green for a split-cadence strategy over many nights,
>    including a resize week, a kickoff that is not a month start, a split inside the month, and a
>    stopped-out position (not re-bought on a resize week).
> 4. **Existing strategies are untouched.** Every current roster entry has no `resize_cadence`:
>    their nights, records, replays and spec digests (`tests/test_paper_roster.py::PINS`) do not
>    move. Backtest code (`book_runner.run_book`, `_rescaled`, `sim/*`) is a closed record: reuse it,
>    do not change its behaviour.
> 5. **Fractional twin preset.** Paper book strategies trade fractional shares
>    (`MONTHLY_HOLD_FRAC`, migration 010; `promote --fractional` maps a variant's rules to its
>    fractional preset via `commands/promote.py` `fractional_twin`). Add
>    `MONTHLY_RANK_WEEKLY_RESIZE_FRAC` (append to `PRESETS`) so a split-cadence lab winner can be
>    promoted with `--fractional`.
> 6. **The site says when it trades.** Positions' copy assumes monthly
>    (`web/app/(app)/positions/page.tsx` ≈ lines 158, 166, 374: "rebalances on the first session of
>    each month"). For a split-cadence strategy it must say, in plain words, that it picks monthly
>    and adjusts how much it holds every week. Positions shows "About $X" per book order (weight ×
>    paper equity); on a resize week the owner needs to see what to trim or top up.
> 7. **Promote refuses nothing it can run, and runs everything it accepts.** After this work a
>    split-cadence candidate must paper-trade end to end; add a test that promotes one into a test
>    database and runs nights.
>
> ## 5. Questions the analysis must settle
>
> - Does the evidence path (`strategies/evidence.py`, Explain) need anything for a resize-only night?
>   A resize night opens no new position, so probably no new evidence; confirm.
> - `book_previews` on a resize night: show the frozen basket at the new exposure, or the fresh
>   allocator pick? (The "would pick now" list exists so a monthly method is never silent.)
> - The weekly trim/top-up threshold is the rules' `RESIZE_BAND` (1% of equity). Is that the
>   owner's practical floor for manual orders in Gotrade with 10,000,000 IDR (about $558)?
> - What the Explain step writes for a resize-only order (it explains new picks only today).

### User-Provided Context
Handover §6 owner context: owner is not a trader (plain words, no ids/codes); 10,000,000 IDR
paper capital; Gotrade takes fractional limit/market orders, TP/SL needs whole shares; every
button icon-only (Lucide) + aria-label + tooltip; commit and push to `main` once verified.
Verification (§7): `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
green except two known Python-3.12-only failures; `engine/.venv/bin/ruff check engine`;
`cd web && npx vitest run && npx tsc --noEmit`. A worktree needs its own `engine/.venv` and
`web/node_modules`.

### User-Provided Files
- `docs/handover/2026-10-07-paper-split-cadence.md`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | `decide_book` accepts split-cadence rules: on a resize-only session it returns exactly `run_book`'s `_with_idle(_rescaled(...))`, given the last rank basket and the book's marks; pure; rank sessions unchanged |
| R2 | The last rank basket is persisted, not recomputed — read back from `book_targets` if exact |
| R3 | Replay agrees: `paper_check` green for a split-cadence strategy over many nights (resize week, mid-month kickoff, split inside the month, stopped-out position not re-bought) |
| R4 | Existing strategies untouched: records, replays, spec digests (`PINS`) do not move; backtest code is a closed record |
| R5 | `MONTHLY_RANK_WEEKLY_RESIZE_FRAC` appended to `PRESETS` so `promote --fractional` maps a split-cadence variant |
| R6 | Positions page says, in plain words, a split-cadence strategy picks monthly and adjusts weekly, and shows what to trim or top up on a resize week |
| R7 | Promote accepts only what paper can run and paper runs everything promote accepts; a test promotes a split-cadence candidate into a test DB and runs nights |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** `paper.book.decide_book` raises `ValueError` for any rule set
with `resize_cadence`, because a resize-only session needs the last rank session's pre-idle
basket and the function is stateless. `run_book` keeps that basket in a loop variable
(`last_rank`). Paper must reproduce that variable across nights from persisted state, feed it to a
pure `decide_book`, and the replay check must agree.

**Success Criteria.**
- A roster entry on `monthly-rank-weekly-resize[-frac|-tbill]` steps through many nights; every
  stored decision equals what `run_book` executes; `paper_check` reports `ok` (or
  `split-affected` where a split on a held symbol makes that the defined status), never `mismatch`.
- `promote --fractional` of a split-cadence variant picks `monthly-rank-weekly-resize-frac`; a test
  promotes one into a test DB and runs nights to a green `paper_check`.
- Every existing roster strategy: same nights, same records, same `PINS`.
- Positions copy for a split-cadence strategy speaks of a monthly pick and a weekly size check,
  and each resize order shows what to trim or add in dollars.

**Key Considerations / assumptions.**
- Only `symbol` and `weight` of `last_rank` reach `_rescaled`'s output (see "Exactness of option
  (a)" below), so split-adjusting the stored rank basket is unnecessary.
- An empty rank basket writes no `book_targets` rows, so "the last rank session" is derived from
  the calendar (rank sessions + kickoff since `paper_start`), not from the presence of rows.

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/handover/2026-10-07-paper-split-cadence.md`

### Discovered Related Files
- `engine/src/seer_engine/sim/rules.py` — presets, `is_rank_session`/`is_resize_session`/`is_decision_session`
- `engine/src/seer_engine/backtest/book_runner.py` — `run_book`, `_rescaled`, `_with_idle` (closed record)
- `engine/src/seer_engine/paper/book.py` — `decide_book`, `needs_kickoff`, `settle_book`
- `engine/src/seer_engine/paper/replay.py` — `expected_book` decisions loop
- `engine/src/seer_engine/paper/store.py` — `save_book_decision`, `read_book_targets`, `load_book`, `_rewrite_executed_targets`, `write_kickoff`, `PaperState.kickoff_session`
- `engine/src/seer_engine/commands/paper.py` — `_start`, `_step_book`, `_evidence`
- `engine/src/seer_engine/commands/promote.py` — `fractional_twin`, `_check_rules`, `build_promotion`
- `engine/src/seer_engine/commands/explain.py` — book target selection (new entries only)
- `engine/src/seer_engine/sim/__init__.py` — re-exports presets
- `engine/src/seer_engine/sim/book.py` — `apply_book_split` (weight unchanged)
- `engine/tests/test_paper_book.py:641` — `test_decide_book_refuses_a_split_cadence_rule_set` (must be replaced)
- `engine/tests/test_paper_kickoff.py`, `test_sim_rules.py:102` (preset id list), `test_promote_command.py:351`, `test_paper_command.py`, `test_paper_check.py`, `test_paper_roster.py::PINS`
- `web/app/(app)/positions/page.tsx` — lines 158, 166, 374, `OrderRow` 395–410
- `web/lib/data.ts` — `Holding`, `PendingOrder`, `Pending`, `pendingOrders`, `Preview`
- `web/lib/strategy.ts` — `Strategy.rulesId`

---

## Current Dataflow

### Entry Point: the paper night

**Location:** `engine/src/seer_engine/commands/paper.py:158` `execute` → `_night` → `_trade` (404)
**Trigger:** `python -m seer_engine paper` after a successful bars run.

#### First night — `_start` (paper.py:515)
1. `store.freeze_spec`, `store.init_paper_state` (day-0 snapshot at `rd.data_date`).
2. Book engine (559–566): `kickoff = needs_kickoff(e.rules, paper_start, paper_start, None)`;
   `targets, _ = decide_book(view, e.obj, e.params, e.rules, rd.data_date, frozenset(), force=kickoff)`;
   evidence for every target symbol (`_evidence`, idle skipped); `store.save_book_decision(..., paper_start, targets, evidence=facts)`;
   `store.write_kickoff` when kicked off; `store.save_book_preview(... targets ...)`.

#### Later nights — `_step_book` (paper.py:591)
For each session `s` after `state.last_session` through `rd.data_date`:
1. `settle_book(book, s, bars, targets, idle_added, rules, divs, splits, last_bar_date)` with the
   targets loaded from the previous night (`store.load_book` → `read_book_targets(pending_session)`).
2. `store.save_book_night(... executed_targets=night.targets)` — rewrites `s`'s stored targets into
   post-split units (`_rewrite_executed_targets`, store.py:950: same symbols, weight and prices updated).
3. `nxt = next_session(s)`; `kickoff = needs_kickoff(rules, paper_start, nxt, kicked)`;
   `targets, idle_added = decide_book(view, e.obj, e.params, rules, s, book.held(), force=kickoff)`.
4. `_evidence` for target symbols; `store.save_book_decision(conn, e.id, nxt, targets, evidence=facts)`;
   kickoff recorded once.
5. On the last session only: preview = `targets` if not None else `decide_book(..., force=True)`;
   `store.save_book_preview`.

### Processing chain: `decide_book` (paper/book.py:135)
- Type checks; `session = next_session(data_date)`.
- **Line 178: `if rules.resize_cadence is not None: raise ValueError(... "paper trading cannot decide them yet" ...)`** — the refusal.
- `if not force and not is_decision_session(rules, session): return None, False`.
- `members_on(data_date)`, `mine = held - {idle}`, history cut at `data_date`; `MarketAware`
  branch via `prepare_for`; else `allocator.targets(...)`.
- `return _with_idle(market, rules, tuple(wanted), data_date)`.

### `run_book` resize mechanics (book_runner.py:270–300, closed record)
```
rank = is_rank_session(rules, session) or session == kickoff
if rank or (last_rank is not None and is_resize_session(rules, session)):
    members/mine/wanted as decide_book
    if rank: last_rank = tuple(wanted); basket = last_rank
    else:    marks = {p.symbol: p.mark for p in book.positions}
             basket = _rescaled(market, last_rank, tuple(wanted), mine, data_date, marks)
    targets, idle_added = _with_idle(market, rules, basket, data_date)
```
`book` there is the book after `data_date` settled — the same `book` paper holds at night.

### `_rescaled` (book_runner.py:114)
- `kept = [t for t in last_rank if t.symbol in held]`; `()` if none.
- `rank_total = Σ last_rank.weight` (all of last_rank, not just kept); `()` if ≤ 0.
- `k = Σ fresh.weight / rank_total`.
- per kept target: `weight = scale_weight(t.weight, k)` (None → dropped);
  `last = q(market.bar(symbol, data_date).close)` or `marks.get(symbol, t.last)`;
  `replace(t, weight, last, limit=None, stop=None, take=None)`.

### `needs_kickoff` (paper/book.py:209)
`False` if a kickoff is stored or `is_decision_session(rules, session)`; else True when no rank
session lies in `[paper_start, session)`. For a split rule set a resize-only Monday is a decision
session, so a clock starting on one would NOT kick off there; `run_book` treats a resize session
before the first rank as no decision, so that Monday trades nothing and the kickoff lands on
Tuesday. For every rule set without `resize_cadence`, `is_decision_session == is_rank_session`.

### Replay — `expected_book` (paper/replay.py:314)
- `run_rules(market, allocator, params, rules, start, last, prepared, dividends, usd_idr, kickoff=head.kickoff, initial_idr)` → snapshots, fills, trades, open positions — `run_book` already handles split cadence.
- Decisions loop (≈ line 360): for each session in `[start, pending]` that is the kickoff or
  `is_decision_session`: `decide_book(market, ..., prev_session(session), held_before(fills, session), force=kickoff)`;
  empty decisions omitted. **This calls the refusing `decide_book`.** It has no last-rank basket
  and no marks; `last_close(market, symbol, d)` exists in the module.

### Data Persistence
- `book_targets (strategy_id, session_date, rank)`: every decision, idle last when added; weight
  at `WEIGHT_QUANTUM` (`_exact` refuses inexact), `last/limit/stop/take` prices, `evidence`
  jsonb, `explanation`. Empty decision → no rows (`pending_decision` true though).
- `paper_state.kickoff_session` (008), `pending_session`, `pending_decision`.
- `book_previews` (008): replaced nightly, display only.

### Exit Points
- Web reads `paper_state` + `book_targets` (`web/lib/data.ts` `pendingOrders`) and `book_previews`.
- `commands/explain.py`: explains `book_targets` of the pending session whose symbol is **not**
  in `book_positions` and whose evidence is non-empty.

---

## Exactness of option (a) — reading the last rank basket back from `book_targets`

1. `_rescaled` uses from `last_rank`: `symbol`, `weight`, and `t.last` **only** as the default of
   `marks.get(t.symbol, t.last)`. That call is reached only for `t` in `kept`, i.e. `t.symbol ∈ held`,
   and `held = mine ⊆ book.held()`, whose every symbol is a key of `marks` (`{p.symbol: p.mark for p in book.positions}`).
   So `t.last` never reaches the output. `limit/stop/take` are dropped.
2. Weights are unit-free: `apply_book_split` keeps weight unchanged ("last, limit, stop and take
   rescaled, weight unchanged", sim/book.py:841); `_rewrite_executed_targets` rewrites prices only
   in effect. A split between the rank and the resize changes nothing `_rescaled` reads.
3. Stored weights are exact: `save_book_decision` stores `_exact(weight, WEIGHT_QUANTUM)`, which
   raises on any weight not already at the quantum; read-back is the same Decimal.
4. Pre-idle: `_with_idle` only appends one target, last, with `symbol == rules.idle_symbol`; an
   allocator targeting the idle symbol is a ValueError. Stripping a trailing idle row is exact.
5. Order: `read_book_targets` returns rank order = the allocator's order; `_rescaled` preserves it.
6. Which session: rows are absent for an empty rank decision, so the session is computed from the
   calendar: the latest `d` in `[paper_start, session)` with `is_rank_session(rules, d)` or
   `d == kickoff_session`. Every such `d` was decided by paper (paper decides every session in
   order), so rows-or-none at `d` is the exact basket (`()` when none). `None` (no rank yet) only
   before the first decision.

Conclusion: (a) is exact; no new column or table.

## Dependencies
- Postgres test DB (`PG_TEST_URL`), per-worktree `engine/.venv` (`python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`), `web/node_modules` (`npm ci`).
- No env/config changes; no migration.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `decide_book` refusal | engine/src/seer_engine/paper/book.py:178 | def | paper |
| `decide_book` | engine/src/seer_engine/commands/paper.py:561, 627, 637 | call | commands |
| `decide_book` | engine/src/seer_engine/paper/replay.py:≈364 | call | paper |
| `needs_kickoff` | engine/src/seer_engine/paper/book.py:209; commands/paper.py:560, 626 | def/call | paper |
| `is_decision_session` | engine/src/seer_engine/paper/replay.py:≈362 | call | paper |
| `_rescaled`, `_with_idle` | engine/src/seer_engine/backtest/book_runner.py:114, 162 | def (reuse) | backtest |
| `MONTHLY_RANK_WEEKLY_RESIZE*` | engine/src/seer_engine/sim/rules.py:179–196; sim/__init__.py:59–62 | def/export | sim |
| `fractional_twin` | engine/src/seer_engine/commands/promote.py:127 | def | commands |
| preset id list | engine/tests/test_sim_rules.py:≈95–110 | test | tests |
| refusal test | engine/tests/test_paper_book.py:641 | test | tests |
| fractional twin test | engine/tests/test_promote_command.py:351 | test | tests |
| kickoff tests | engine/tests/test_paper_kickoff.py | test | tests |
| `PINS` | engine/tests/test_paper_roster.py:77 | test | tests |
| monthly copy | web/app/(app)/positions/page.tsx:158, 166, 374 | ui | web |
| `About` cell | web/app/(app)/positions/page.tsx:404 | ui | web |
| `Strategy.rulesId` | web/lib/data.ts:47, 78 | data | web |
| Explain book selection | engine/src/seer_engine/commands/explain.py:87 | sql | commands |

## Impact Points (files that WILL need changes)
1. `engine/src/seer_engine/sim/rules.py`, `sim/__init__.py` — `MONTHLY_RANK_WEEKLY_RESIZE_FRAC` (phase 1)
2. `engine/src/seer_engine/paper/book.py` — `decide_book` split path, `needs_kickoff`, last-rank helpers (phase 1)
3. `engine/src/seer_engine/paper/replay.py` — decisions loop carries last rank + marks (phase 1)
4. `engine/tests/test_paper_book.py`, `test_paper_kickoff.py`, `test_sim_rules.py`, `test_promote_command.py`, `test_paper_replay.py` (phase 1)
5. `engine/src/seer_engine/commands/paper.py` (+ maybe `paper/store.py` read helper) — wiring (phase 2)
6. new `engine/tests/test_paper_split_cadence.py` — multi-night + paper_check + promote end to end (phase 2)
7. `web/lib/strategy.ts` (or a new `web/lib/cadence.ts`), `web/app/(app)/positions/page.tsx`, tests (phase 3)

**This document describes. The plan files prescribe.**

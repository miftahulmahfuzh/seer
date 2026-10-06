# Handover: nightly paper trading for split-cadence rules (monthly pick, weekly resize)

Written 2026-10-07 on `main` after `lab(M0022)` was pre-registered. Pass this file straight to
`/analyze` in a fresh session and read all of it first. Like the earlier handovers, it separates:
- decisions that are **already made**;
- facts that were **verified** (with file:line);
- questions the analysis still has to settle.

---

## 0. In plain words

Some lab methods pick their stocks once a month but re-check how much to hold every week. The
backtest engine already runs them. The nightly paper engine refuses them, on purpose, because it
does not remember last month's basket between nights. The owner has said a weekly check is fine
if it performs better (2026-10-07), and lab method M0022 (RM's book with its volatility brake read
weekly) is the first candidate that needs this. If M0022, or any later method on a split-cadence
rule set, passes the lab and gets promoted, the paper night must be able to run it. This handover
is that missing feature, built before it is needed, so a promotion is never blocked on it.

Nothing here changes what any current roster strategy does. Every roster entry today
(`SPY`, `A`, `C`, `F4-MOM12-N20-TREND-FR`, `F1-SPY-SMA200-M-FR`, `RM-FR`) uses rules without a
`resize_cadence`, and their decisions, records and digests must stay byte for byte.

---

## 1. What a split-cadence rule set is (verified)

- `sim/rules.py:179` — `MONTHLY_RANK_WEEKLY_RESIZE = replace(MONTHLY_HOLD, id="monthly-rank-weekly-resize", resize_cadence="weekly")`,
  and `MONTHLY_RANK_WEEKLY_RESIZE_TBILL` next to it. Both are in `PRESETS`.
- `sim/rules.py` `is_rank_session(rules, s)`: the first session of a `cadence` period (monthly).
  `is_resize_session(rules, s)`: the first session of a `resize_cadence` period (weekly) that is
  not also a rank session. `is_decision_session` = rank or resize.
- On a **rank** session the allocator picks a new basket (as today).
- On a **resize-only** session the basket is frozen to the last rank's basket; only its total
  exposure moves. `backtest/book_runner.py` `run_book` (≈ lines 270–300) does this:
  - it keeps `last_rank`: the last rank session's targets, **before** `_with_idle` adds the idle
    instrument; `None` until the first rank;
  - on a resize session it calls the allocator anyway (`wanted`), then
    `basket = _rescaled(market, last_rank, wanted, mine, data_date, marks)`;
  - a resize session before the first rank is not a decision.
- `book_runner._rescaled` (≈ line 114): keeps every `last_rank` target still **held**, multiplies
  its weight by `k = Σ fresh weights / Σ last_rank weights`, refreshes `last` to the close on
  `data_date` (falling back to the book's mark), and drops `limit`/`stop`/`take`. A resize session
  opens nothing new; a stock that left the book (stopped out, force-closed) is not bought back.
- The kickoff (migration 008, `paper.book.needs_kickoff`, `run_book(kickoff=...)`) counts as a
  rank session in `run_book`: `rank = is_rank_session(rules, session) or session == kickoff`, so
  `last_rank` is set on the kickoff too.

## 2. Why paper refuses it today (verified)

- `paper/book.py` `decide_book` (≈ line 178): `if rules.resize_cadence is not None: raise ValueError(...)`
  with the message "paper trading cannot decide them yet (the last rank session's basket is not
  stored)". Its docstring explains: a resize-only session needs the last rank's basket and
  `decide_book` is stateless.
- `commands/paper.py` `_start` and `_step_book` call `decide_book` every night, so a roster entry
  on these rules would fail the **whole** paper night (one transaction for every strategy).
- `commands/promote.py` would accept such a candidate today (the rules are a preset), so a lab
  promotion could put a row on the roster that breaks the night. That gap is part of this work.

## 3. What already exists that helps (verified)

- `book_targets` stores every decision by `(strategy_id, session_date, rank)`
  (`db/migrations/003_paper.sql`); `store.save_book_decision` writes it, `store.read_book_targets`
  reads one session's rows in rank order. Rank decisions are therefore already persisted.
- When `_with_idle` appended the idle instrument, it is the **last** target, and
  `LoadedBook.idle_added` says so (`store.load_book`); stripping it gives the pre-idle basket.
- Splits: `store.save_book_night(..., executed_targets=...)` rewrites the executed session's stored
  targets into post-split units (`_rewrite_executed_targets`), and `sim.book.apply_book_split`
  rescales targets. A stored rank basket used weeks later may need the splits applied since.
- `paper/replay.py` `expected_book` already replays with `run_rules` → `run_book`, which supports
  split cadence. Its expected-**decisions** loop (≈ line 360) calls `decide_book` per decision
  session and would hit the same refusal.
- `paper_state.kickoff_session` (008) and `paper.book.needs_kickoff`: a split-cadence strategy whose
  clock starts mid-month kicks off with a rank, which must become its `last_rank`.
- `book_previews` (008) and evidence (009): the preview path calls `decide_book(force=True)`.

## 4. The work (decisions already made)

1. **`decide_book` accepts split-cadence rules.** It takes the last rank basket (pre-idle, in
   current units) and the book's marks, and on a resize-only session returns exactly what
   `run_book` would execute: `_with_idle(_rescaled(...))`. On a rank session nothing changes. The
   function stays pure (it lives under `paper/`, purity-tested).
2. **The last rank basket is persisted, not recomputed.** Recomputing from history would be a
   second source of truth. Decide in the analysis between (a) reading it back from `book_targets`
   of the last rank session (pre-idle, split-adjusted to now), or (b) a new column/table. Prefer
   (a) if it is exact; record why if not.
3. **Replay agrees.** `paper_check` must stay green for a split-cadence strategy over many nights,
   including a resize week, a kickoff that is not a month start, a split inside the month, and a
   stopped-out position (not re-bought on a resize week).
4. **Existing strategies are untouched.** Every current roster entry has no `resize_cadence`:
   their nights, records, replays and spec digests (`tests/test_paper_roster.py::PINS`) do not
   move. Backtest code (`book_runner.run_book`, `_rescaled`, `sim/*`) is a closed record: reuse it,
   do not change its behaviour.
5. **Fractional twin preset.** Paper book strategies trade fractional shares
   (`MONTHLY_HOLD_FRAC`, migration 010; `promote --fractional` maps a variant's rules to its
   fractional preset via `commands/promote.py` `fractional_twin`). Add
   `MONTHLY_RANK_WEEKLY_RESIZE_FRAC` (append to `PRESETS`) so a split-cadence lab winner can be
   promoted with `--fractional`.
6. **The site says when it trades.** Positions' copy assumes monthly
   (`web/app/(app)/positions/page.tsx` ≈ lines 158, 166, 374: "rebalances on the first session of
   each month"). For a split-cadence strategy it must say, in plain words, that it picks monthly
   and adjusts how much it holds every week. Positions shows "About $X" per book order (weight ×
   paper equity); on a resize week the owner needs to see what to trim or top up.
7. **Promote refuses nothing it can run, and runs everything it accepts.** After this work a
   split-cadence candidate must paper-trade end to end; add a test that promotes one into a test
   database and runs nights.

## 5. Questions the analysis must settle

- Does the evidence path (`strategies/evidence.py`, Explain) need anything for a resize-only night?
  A resize night opens no new position, so probably no new evidence; confirm.
- `book_previews` on a resize night: show the frozen basket at the new exposure, or the fresh
  allocator pick? (The "would pick now" list exists so a monthly method is never silent.)
- The weekly trim/top-up threshold is the rules' `RESIZE_BAND` (1% of equity). Is that the
  owner's practical floor for manual orders in Gotrade with 10,000,000 IDR (about $558)?
- What the Explain step writes for a resize-only order (it explains new picks only today).

## 6. Owner context

- The owner is not a trader; site text is plain words, no ids or codes.
- Owner money: 10,000,000 IDR; paper books start with the same (`paper/capital.py`).
- Gotrade takes fractional limit/market orders; its take-profit/stop-loss order needs whole shares.
- Every button on the site is icon-only (Lucide) with `aria-label` and a tooltip.
- Commit and push to `main` once verified; the repo is public on purpose.

## 7. Verification

`PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
green except the two known Python-3.12-only failures (`test_f_fundamental.py::test_allocator_shape`,
`test_market_fundamentals.py::test_adding_the_hook_does_not_change_the_allocator_check`);
`engine/.venv/bin/ruff check engine`; `cd web && npx vitest run && npx tsc --noEmit`. A worktree
needs its own `engine/.venv` and `web/node_modules`.

# Code Analysis: The paper roster, and promoting a lab method onto it

**Type:** Feature Implementation
**Date:** 2026-10-05T16:50:54+07:00
**Session ID:** 20261005-165054-XGER
**Plan:** `ROSTER_PROMOTION_PIPELINE_PLAN.md` (6 phases)
**Worktree:** `/home/miftah/.worktrees/seer/roster-promotion-pipeline` on `feature/roster-promotion-pipeline` (base `origin/main` @ `0d03490`)

---

## User Input

### Original User Request

Two messages, both verbatim.

The first, challenging the exclusion of fundamentals from paper trading:

> what is the justification that we dont include fundamentals-driven yet? this is just a paper
> trading app. we clearly agrees that i won't use real money until we pass all gates

The second, on the promotion pipeline:

> we also have Sera the method lab .
> i wanted to talk to you about this.
> we are gonna keep exploring new methods overtime, thousands upon thousands of methods,
> approaches, variations, parameters.
> i am thinking that we need to be able to replace the current 4 approaches (A-Quant,
> F4-Momentum, F1-Trend, C-News Veto) easily.
> first, we need a robust pipeline to easily compare and "re-sort" the current SEER's four
> horsemen .
> so , in case tomorrow during one of "/sera-the-explorer" sessions we found a better method, we
> should be able to easily "promote" it to the main app as the new horsemen
> (https://seertrade.site/leaderboard)
> what do you think about this idea?

Then `/analyze these`, where "these" is the scope agreed in the reply: roster-as-data, add/retire
semantics, the common-window leaderboard math, and FND as the first promotion to prove the path.

### User-Provided Context

The user's first message is a **correction of a false claim made in this session**, and the
correction is right. The claim was that fundamentals "isn't ready" for paper because of the
coverage gate. Both halves of that were wrong, and the evidence is in the tree:

- Every strategy on the paper roster **already failed its backtest gate**, and the roster records
  the failure in a dedicated field rather than treating it as disqualifying.
- The `0.3151` coverage figure measured by the `fundamental-panel-coverage` set (landed `3ca3ad0`,
  today) is over the **dev window 1996–2015**. Paper trades on today's filings. XBRL has been
  effectively universal since ~2011, and phase 1 of that set measured 2015 at 9 of 10 sampled
  dates with 519 rankable symbols. Live coverage is not the dev-window figure.

So "it has not passed the gates" was never the roster's admission criterion, and the coverage
number is a backtest-validation fact, not a live-data fact.

### User-Provided Files

None marked with `@`. The targets were named in prose: Sera the method lab, the four horsemen
(A-Quant, F4-Momentum, F1-Trend, C-News Veto), and `https://seertrade.site/leaderboard`.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Include the fundamentals-driven strategy in paper trading — the stated justification for excluding it does not hold, because paper trading is not real money and the gates bind only the real-money decision |
| R2 | Be able to replace the four horsemen easily — swapping an approach must not require editing engine code |
| R3 | A robust pipeline to compare and "re-sort" the current horsemen, so a better method can be recognised as better |
| R4 | Promote a method found in a `/sera-the-explorer` session onto the main app's leaderboard as a new horseman |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement**

The paper roster is a compiled-in Python tuple. Adding, replacing or retiring a strategy means
editing `engine/src/seer_engine/paper/roster.py`, writing a migration for the display row, and
deploying. The method lab produces candidates on a completely separate substrate — a committed
SQLite database with its own `methods`/`trials` tables — and there is no path from one to the
other. The user intends to generate methods at a volume ("thousands upon thousands") that makes a
code edit per promotion untenable.

**Success Criteria**

1. A strategy can be added to or retired from the paper roster **without an engine code change**.
2. Retiring a horseman **preserves its track record**; it stops trading and stays on the board.
3. The leaderboard can rank strategies that started on **different dates** without that comparison
   being arithmetic nonsense.
4. A lab method can be promoted from Sera onto the roster by a command, not by hand.
5. The fundamentals strategy (`FND`) is on the paper roster, as the first promotion through the
   new path.

**Key Considerations**

- **The freeze is load-bearing and must survive.** `roster.py`'s docstring states it: *"a changed
  strategy needs a new id with its own paper clock, never an edited entry (`paper` refuses a
  started id whose stored digest differs)"*. This is already enforced by `store.check_digest`
  (`commands/paper.py:193`). Making the roster editable must not make it *mutable* — the
  distinction is the whole value of the paper record.
- **Different inception dates are the central difficulty of R3**, not an edge case. Comparing a
  method that started three months ago to one that started eighteen months ago on raw total return
  measures the market, not the method.
- **`REGISTRY` must not become the promotion target.** It is the P7a dev-run candidate set, fixed
  before that run, capped at 60 (`dev.MAX_CANDIDATES`), with `candidate_digest` pinned in
  `tests/test_registry.py`. Appending promoted methods to it would corrupt the multiple-testing
  count that the lab's `trials` table exists to maintain.
- **Lab and paper live in different databases.** The lab is `lab/lab.sqlite` (committed,
  append-only, triggers refusing UPDATE/DELETE); paper is Neon. The bridge crosses a process and a
  storage boundary.

**Assumptions**

- Promotion volume at the *roster* is low even when lab volume is high: a funnel, not a firehose.
  The roster is the narrow end.
- The user wants the leaderboard to stay honest more than they want it to stay simple; the reply
  that prompted `/analyze these` argued exactly that and was accepted.

---

## Analysis Scope

### Explicitly Mentioned Files

None (`@`-free prose). Targets resolved by name.

### Discovered Related Files

- `engine/src/seer_engine/paper/roster.py` — the frozen roster (the subject of R2)
- `engine/src/seer_engine/paper/store.py` — `check_digest`, `freeze_spec`, paper state I/O
- `engine/src/seer_engine/commands/paper.py` — the paper night; `plan` (:179) applies the freeze
- `db/migrations/003_paper.sql` — `strategies` columns, `paper_state`, `book_*`, `equity_snapshots`
- `engine/src/seer_engine/backtest/registry.py` — `Candidate`, `REGISTRY`, `candidate_digest`
- `engine/src/seer_engine/strategies/f_fundamental.py` — `FUNDAMENTAL`, id `"FND"` (the subject of R1)
- `engine/src/seer_engine/lab/store.py` — the lab SQLite schema and `snapshot`
- `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py` — the spent fundamentals method
- `web/app/(app)/leaderboard/view.ts` — `looks`, `bestResearch`, `CHECKS`
- `web/lib/data.ts` — `paperStart`, the `strategies` projection
- `web/lib/monthly.ts` — the month-by-month math
- `web/lib/sera/types.ts` — `METHOD_STATUSES`, including `promoted`

---

## Current Dataflow

### Entry Point: the nightly paper run

**Location:** `.github/workflows/nightly.yml`, step `Paper` (:90)
**Trigger:** cron `0 23 * * 1-5` and retry `0 1 * * 2-6`; also `workflow_dispatch`
**Next Step:** `python -m seer_engine paper` → `commands/paper.py`

### Processing Chain

1. **Roster resolution** — `paper/roster.py`
   - **Location:** `roster.py:122` (`ROSTER`)
   - **Input:** nothing. It is a module-level `tuple[RosterEntry, ...]`, built from direct imports
     of `STRATEGY_A`, `STRATEGY_C`, `FACTOR`, `TIMING` and two `REGISTRY` lookups.
   - **Output:** five `RosterEntry` values: `SPY`, `A`, `F4-MOM12-N20-TREND`, `F1-SPY-SMA200-M`, `C`.
   - **This is the single point R2 is about.** There is no database read, no config, no override.

2. **The frozen spec** — `roster.spec` / `spec_text` / `spec_digest`
   - **Location:** `roster.py:254` (`spec`), `:285` (`spec_text`), `:290` (`spec_digest`)
   - **Transform:** the trial-defining parts of an entry → JSON-ready dict of strings → canonical
     text (sorted keys, no whitespace, ASCII) → sha256 hex.
   - **Note:** `spec` takes a plain mapping, so a spec read back from `strategies.params->'spec'`
     recomputes to the same digest. This is what makes a database-stored roster *checkable*.

3. **The freeze check** — `commands/paper.py:plan`
   - **Location:** `commands/paper.py:179`, calling `store.check_digest` at `:193`
   - **Transform:** for each entry, read the `strategies` row; if `paper_start` is set and the
     stored digest differs from the recomputed one, raise `store.SpecMismatch`.
   - **Consequence:** a started strategy whose definition changed is **refused**, not silently
     re-based. Add-not-mutate is already enforced here.

4. **Starting a strategy** — `commands/paper.py:374`
   - `store.freeze_spec` writes the frozen spec and `paper_start = rd.session_date`.
   - Requires a USD/IDR rate on or before the data date, else `PaperError` (:388).

5. **Leaderboard read** — `web/lib/data.ts`
   - **Location:** `data.ts:57` (`paperStart`), `:67` (the SQL projection)
   - Reads `paper_start::text`, `params->'backtest_gate'`, `params->'spec'->>'object'`.

6. **Leaderboard ranking** — `web/app/(app)/leaderboard/view.ts`
   - `bestResearch` (:60): *"Highest total return among research strategies that have one."*
     A single pass taking `max(totalReturn)`. **No window alignment, no risk adjustment, no
     inception handling.** This is the whole of the current "re-sort", and it is what R3 replaces.
   - `looks` (:26): assigns card colours by roster order from `CARD_BGS` (4 entries) and `LINES`
     (4 entries), falling back to `var(--ink-2)` beyond the fourth. Benchmarks are special-cased.

### Data Persistence

**Database (Neon):** `strategies` (id, name, sub, icon, is_champion, is_benchmark, sort, engine,
rules_id, paper_start, params), `paper_state`, `book_positions`, `book_targets`, `book_trades`,
`orders`, `equity_snapshots`, `runs`.
**Database (SQLite, committed):** `lab/lab.sqlite` — `methods`, `trials`, `ideas_seen`, `insights`.
Triggers refuse UPDATE/DELETE on `trials` and `insights`; `methods.status` moves only along
`TRANSITIONS`; `source_sha` is set once.
**Snapshot:** `lab store.snapshot` → `web/data/lab.json` → `seertrade.site/sera`.

### Exit Points

- `strategies` rows and the `paper_*` tables, read by the Next.js app
- `web/data/lab.json`, committed, read by the Sera pages

---

## Key Data Structures

### Dataclass: `RosterEntry`
**Location:** `engine/src/seer_engine/paper/roster.py:69` (`@dataclass(frozen=True, slots=True)`)
**Fields:** `id`, `name`, `sub`, `icon`, `is_champion`, `is_benchmark`, `sort`, `engine`
(`'bracket' | 'book' | 'benchmark'`), `rules`, `obj`, `object_name`, `params`, `registry_id`,
`lookback`, `gate_note`, `gate_applicable`.
**Used In:** `ROSTER` (:122), `spec` (:254), `commands/paper.py` throughout.
**Observation:** `obj` is a live Python object. That is the one field a database row cannot carry,
and therefore the crux of R2 — every other field is already data.

### Tuple: `ROSTER`
**Location:** `roster.py:122`
**Entries:** SPY (benchmark, champion), A (bracket), F4-MOM12-N20-TREND (book), F1-SPY-SMA200-M
(book), C (bracket, `gate_applicable=False`).
**Gate notes, verbatim — the evidence for R1:**

| id | gate_note |
|---|---|
| `SPY` | "Benchmark, not a strategy: it has no backtest gate and is never a Seer pick" |
| `A` | "P3 gate **failed** out of sample (2022-01-03..2026-10-02): -15.0% vs SPY TR +71.9%, PF 0.92, max DD 33.3%" |
| `F4-MOM12-N20-TREND` | "P7a dev window only; **failed** max DD <= 15% (22.2%)" |
| `F1-SPY-SMA200-M` | "P7a dev window only; **failed** max DD <= 15% (18.7%) and >= 100 trades (11)" |
| `C` | "Backtest gate: not applicable (LLM strategy, design §1 item 5)" |

### Dataclass: `Candidate` (the backtest registry)
**Location:** `engine/src/seer_engine/backtest/registry.py:70`
**Fields:** `id`, `allocator` (`Allocator | Strategy`), `params`, and family/label fields.
**Constraint:** `len(REGISTRY) <= dev.MAX_CANDIDATES` (60), *"fixed BEFORE the run"* (:3).
`candidate_digest` (:350) is pinned by `tests/test_registry.py`.

### Allocator: `FUNDAMENTAL` (id `"FND"`)
**Location:** `engine/src/seer_engine/strategies/f_fundamental.py`
**Shape:** a sibling of `f_factor`; ranks on point-in-time SEC filings rather than price history.
Reaches the panel through `prepare_market(market)` reading `market.fundamentals`, which is what
makes it satisfy the `MarketAware` protocol (`lab/runner.py:79` names it explicitly).
**Important property, from its own docstring:** `targets(history, ...)` and `prepare(history)` see
no panel, so with no panel **no symbol is eligible and both return `()`** — *"the correct reading
of 'nothing is known about any filer', not a bug and not a silent zero."* A fundamentals entry on
a `Market` without a panel trades nothing rather than trading wrongly.
**Eligibility on date d:** member on d and not SPY; a bar dated d; at least
`fundamental_lookback(params)` bars through d; `close >= min_price`; 20-day mean close×volume
> `min_dollar_volume`; a panel fact filed on or before d and no more than `max_stale_days` before
d; and every factor the chosen ranking reads is finite.

### Lab tables
**Location:** `engine/src/seer_engine/lab/store.py:1-27` (docstring)
- `methods` — one row per idea; `status` along `TRANSITIONS`; `analysis` only grows; `hypothesis`
  frozen once the method leaves `idea`; `source_sha` set once.
- `trials` — one row per backtest, **the multiple-testing count**; `UNIQUE(config_digest, window)`
  so a configuration runs at most once on dev and gets at most one look at test.

### Web: `METHOD_STATUSES`
**Location:** `web/lib/sera/types.ts:120`
**Values:** `idea`, `registered`, `rejected`, `dev-eligible`, `promoted`, `test-passed`, …
**Observation:** `promoted` already exists as a lab status. What does not exist is any consumer
that turns a `promoted` method into a paper roster entry.

---

## Dependencies

### Configuration / Environment
- `DATABASE_URL_UNPOOLED` (Neon) for the paper tables; `.env.local-train` for the local train DB.
- `.github/workflows/nightly.yml` secrets gate at step `Check secrets` (:36).

### External Services
- Neon (paper, strategies, equity snapshots)
- Vercel (`seertrade.site`)
- SEC EDGAR (fundamentals; already ingested to the 2009 floor by `3ca3ad0`)

---

## Reference List

Every site that defines or consumes the roster, the ranking, or the lab→paper boundary.

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `RosterEntry` | `engine/src/seer_engine/paper/roster.py:69` | def | `paper` |
| `ROSTER` | `engine/src/seer_engine/paper/roster.py:122` | def | `paper` |
| `ROSTER_IDS` | `engine/src/seer_engine/paper/roster.py:214` | def | `paper` |
| `spec` / `spec_text` / `spec_digest` | `roster.py:254,285,290` | def | `paper` |
| `MAX_LOOKBACK_BARS` | `roster.py` (docstring :39) | def | `paper` |
| `plan` (freeze checks) | `engine/src/seer_engine/commands/paper.py:179` | call | `commands` |
| `store.check_digest` | `commands/paper.py:193` | call | `paper` |
| `store.freeze_spec` | `commands/paper.py:393` | call | `paper` |
| unknown-engine guard | `commands/paper.py:340` | call | `commands` |
| `strategies.paper_start` | `db/migrations/003_paper.sql:8` | config | `db` |
| `strategies.engine` CHECK | `db/migrations/003_paper.sql:6` | config | `db` |
| `paper_state` | `db/migrations/003_paper.sql:17` | config | `db` |
| `Candidate` / `REGISTRY` | `engine/src/seer_engine/backtest/registry.py:70,91` | def | `backtest` |
| `candidate_digest` | `backtest/registry.py:350` | def | `backtest` |
| `FUNDAMENTAL` (`"FND"`) | `engine/src/seer_engine/strategies/f_fundamental.py` | def | `strategies` |
| `MarketAware` note | `engine/src/seer_engine/lab/runner.py:79` | doc | `lab` |
| lab `methods` / `trials` | `engine/src/seer_engine/lab/store.py:7-16` | def | `lab` |
| `bestResearch` | `web/app/(app)/leaderboard/view.ts:60` | def | `web` |
| `looks` / `CARD_BGS` / `LINES` | `web/app/(app)/leaderboard/view.ts:16,17,26` | def | `web` |
| `CHECKS = 6` | `web/app/(app)/leaderboard/view.ts` | def | `web` |
| `paperStart` projection | `web/lib/data.ts:57,67` | call | `web` |
| `METHOD_STATUSES` | `web/lib/sera/types.ts:120` | def | `web` |
| demo seed roster | `web/scripts/seed-demo.mjs:307` | test | `web` |
| roster↔migration equality test | `engine/tests/test_paper_roster.py` | test | `engine` |

---

## Impact Points (files that WILL need changes)

1. `db/migrations/006_roster.sql` *(new)* — `strategies.status`, `paper_end`, `promoted_from`; the
   roster rows become data. **Phase 1.**
2. `engine/src/seer_engine/paper/roster.py` — resolve entries from database rows through a name→object
   resolver instead of a compiled tuple; keep `spec`/`spec_digest` byte-identical. **Phase 1.**
3. `engine/src/seer_engine/paper/store.py` — read/write `status` and `paper_end`. **Phases 1, 2.**
4. `engine/src/seer_engine/commands/paper.py` — skip retired entries; start newly active ones;
   the freeze check is unchanged. **Phase 2.**
5. `engine/src/seer_engine/paper/compare.py` *(new)* — common-window, risk-adjusted comparison over
   `equity_snapshots`. **Phase 3.**
6. `web/app/(app)/leaderboard/view.ts` + `page.tsx` — variable roster size, retired presentation,
   the re-sort. **Phase 4.**
7. `web/lib/data.ts` — project `status`, `paper_end`. **Phase 4.**
8. `engine/src/seer_engine/commands/promote.py` *(new)* — the lab→roster bridge. **Phase 5.**
9. `engine/src/seer_engine/lab/store.py` — record the promotion against the method. **Phase 5.**
10. `engine/src/seer_engine/paper/roster.py` (resolver table) + a roster row for `FND`. **Phase 6.**
11. `engine/tests/test_paper_roster.py` — the pinned digests and the migration-equality test must
    keep passing across all of it. **Every phase.**

**This document describes. The plan files prescribe.**

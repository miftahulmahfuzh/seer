# Plan: The roster promotion pipeline

**Slug:** roster-promotion-pipeline
**Date:** 2026-10-05T16:50:54+07:00
**Analysis:** `20261005-165054-XGER_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/roster-promotion-pipeline`
**Branch:** `feature/roster-promotion-pipeline` (base: `origin/main` @ `0d03490`)
**Phases:** 6
**Status:** reconciled — phases 1, 2, 3, 4, 5 of 6 complete
**Coordinator:** —

---

## Why

Verbatim from the user, across two messages.

On the fundamentals exclusion:

> what is the justification that we dont include fundamentals-driven yet? this is just a paper
> trading app. we clearly agrees that i won't use real money until we pass all gates

On the promotion pipeline:

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

**The first message is a correction, and it stands.** This session claimed fundamentals was not
ready for paper because of the coverage gate. That was wrong twice over, and the tree proves both:
every strategy on the roster already failed its gate and says so in a dedicated `gate_note` field,
and the `0.3151` coverage figure is over the **dev window 1996–2015**, not over live 2026 filings.
R1 exists because the exclusion had no valid justification, not because a new argument was found.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Include the fundamentals-driven strategy in paper trading — the stated justification for excluding it does not hold, because paper is not real money and the gates bind only the real-money decision | **6** |
| R2 | Replace the four horsemen easily — swapping an approach must not require editing engine code | **1, 2** |
| R3 | A robust pipeline to compare and "re-sort" the horsemen, so a better method can be recognised as better | **3, 4** |
| R4 | Promote a method found in a `/sera-the-explorer` session onto the main app's leaderboard | **5** |

**This map survived reconciliation unchanged.** No step moved between phases, so no `R` moved
either; every phase's `Satisfies` line is the one its planner wrote. What changed was *how* phases
do their work, not *which* requirement they serve. Every `R` has at least one owner and no phase's
steps serve an `R` outside its own line — the two creep candidates were checked and both are
inside their phase's requirement: phase 4's `spyOverSpan` fix to the "Beats SPY" checklist row is
invariant 6 and therefore R3, and phase 6's `decide_book` dispatch is what makes `FND` able to
trade at all and therefore R1.

Two notes on this map:

- **R2 is two phases because "replace" is two capabilities.** Phase 1 makes the roster *readable*
  from data; phase 2 makes it *changeable* over time (retire, activate) without rewriting history.
  Either alone leaves R2 half-served.
- **R3 is two phases because the math and its presentation fail differently.** Phase 3 can be wrong
  and still render; phase 4 can be right and still mislead. They are split so the math is testable
  without a browser.

## Scope

**In scope**

- `db/migrations/006_roster.sql` *(new)* — `strategies.status`, `paper_end`, `promoted_from`,
  `object_name`, `registry_id`, `gate_note`, `gate_applicable`.
- `engine/src/seer_engine/paper/roster.py` — entries resolved from database rows through a
  name→object resolver; `spec`/`spec_text`/`spec_digest` unchanged byte for byte.
- `engine/src/seer_engine/paper/store.py` — `status` and `paper_end` I/O, `read_roster_rows`.
- `engine/src/seer_engine/commands/paper.py`, `commands/paper_check.py` — read the roster from
  rows; skip retired, start newly active.
- `engine/src/seer_engine/paper/compare.py` *(new)* and `commands/compare.py` *(new)* —
  common-window, risk-adjusted comparison and its read-only CLI.
- `engine/src/seer_engine/commands/promote.py` *(new)* — the lab→roster bridge.
- `engine/src/seer_engine/lab/store.py` — record a promotion against the method.
- `web/lib/data.ts`, `web/app/(app)/leaderboard/{view.ts,page.tsx,leaderboard.module.css}` —
  variable roster, retired presentation, the re-sort.
- `engine/src/seer_engine/paper/{book.py,replay.py}` — the `MarketAware` dispatch, without which a
  fundamentals strategy on the roster holds cash forever while claiming to have decided.
- `db/migrations/007_fnd.sql` *(new)* and a roster row for `FND`
  (`strategies/f_fundamental.py`'s `FUNDAMENTAL`).

**Out of scope, and why**

- **`backtest/registry.py` is never appended to.** `REGISTRY` is the P7a dev-run candidate set,
  *"fixed BEFORE the run"*, capped at 60 (`dev.MAX_CANDIDATES`), with `candidate_digest` pinned in
  `tests/test_registry.py`. Promoting into it would corrupt the multiple-testing count the lab's
  `trials` table exists to maintain. See `## Decisions`, row D1.
- **No existing paper clock is reset, and no started strategy is edited.** The freeze
  (`store.check_digest`) stays exactly as it is.
- **No real-money path.** Nothing in this set moves money or changes the go-live checklist's
  meaning. The gates still bind that decision; they do not bind roster membership.
- **No change to the lab's own gates, `trials` uniqueness, or `source_sha` freezing.**
- **No re-run of M0005 and no new method id minted.** Phase 6 puts the *allocator* `FND` on the
  roster; it does not resurrect the spent lab method.
- **Automatic promotion.** Every promotion in this set is a human-invoked command. A Sera session
  may *recommend*; it does not write the roster.

## Invariants

Every phase must hold all of these. They are checkable, not felt.

1. **The tree builds and the suite passes at the end of each phase.** Baseline at `0d03490`:
   **2261 passed, 332 skipped** (`"$SEER_PY" -m pytest engine/tests -q`), and **2593 passed, 0
   skipped** with `PG_TEST_URL` exported. **Each phase reports a DELTA off what it inherited,
   never an absolute** — the phases land in a swarm. No phase may reduce the passing count, and no
   existing test may change its result.
2. **`spec_digest` is byte-stable for every strategy that already has a `paper_start`.**
   `roster.spec` / `spec_text` / `spec_digest` must produce identical output for `SPY`, `A`,
   `F4-MOM12-N20-TREND`, `F1-SPY-SMA200-M` and `C` before and after every phase. The digests
   pinned in `engine/tests/test_paper_roster.py` keep passing **unchanged**. A phase that needs to
   change a pinned digest has misunderstood its task.
3. **Add and retire; never mutate.** No phase may edit a started strategy's definition in place.
   `store.check_digest`'s `SpecMismatch` refusal stays live and stays reachable. A changed strategy
   is a new id with its own paper clock.
4. **A retired strategy keeps its history.** Retirement sets `paper_end` and stops trading. It
   never deletes `equity_snapshots`, `orders`, `book_*` or `paper_state` rows, and the strategy
   stays visible on the leaderboard marked retired.
5. **Migrations are additive only.** Nullable or defaulted columns and new tables, matching
   `003_paper.sql`'s own stated discipline. No column is dropped, no CHECK is narrowed, and
   migrations 001–005 are not edited.
6. **Any ranking that mixes strategies with different `paper_start` dates states its window.**
   No phase may compare raw total return across unequal windows and present it as a ranking. This
   is R3's whole point; violating it silently is worse than not shipping it.
7. **The roster's display rows and the engine agree.** `engine/tests/test_paper_roster.py` checks
   roster entries against a migrated database; that equality holds after every phase.
8. **No network write outside the databases the repo already names**, no `lab run`, no real-money
   path, and no Neon write from a test. `conftest.py` gives each DB test a throwaway schema.
9. **A roster entry whose object cannot be resolved is a hard error, never a skip.** A typo in a
   resolver name must stop the paper night with a named error, not silently drop a portfolio and
   leave a gap in its equity curve.

## Runtime preamble

Every phase plan opens with this block and every command in this set assumes it.

```bash
export SEER_WT=/home/miftah/.worktrees/seer/roster-promotion-pipeline
export SEER_PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$SEER_WT/engine/src                        # wins over the editable .pth
export SEER_MAIN=/home/miftah/seer
export SEER_ENV_FILE=$SEER_MAIN/.env.local-train             # ABSOLUTE, always
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
cd "$SEER_WT"
"$SEER_PY" -c 'import seer_engine, pathlib; print(pathlib.Path(seer_engine.__file__).resolve())'
# must print $SEER_WT/engine/src/seer_engine/__init__.py
```

Measured on the `fundamental-panel-coverage` set that landed today: the worktree has **no venv of
its own**, `/home/miftah/seer/engine/.venv` is an *editable* install pointing at
`/home/miftah/seer/engine/src`, and `engine/pyproject.toml` sets `testpaths` but no `pythonpath`.
Without `PYTHONPATH` a phase can edit this worktree and watch `main`'s code pass the tests.

For `web/`: `cd $SEER_WT/web && npm ci` once, then `npm test` and `npm run build`.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 ✅ | The roster becomes data: `status`, `paper_end`, and a name→object resolver | R2 | `db`, `engine/src/seer_engine/paper` | 4 | — | HARD | `.workflows/plan/roster-promotion-pipeline/phase-1.md` | P1-ENG-7KQ2 | — |
| 2 ✅ | Retire and activate: the paper night honours roster lifecycle | R2 | `engine/src/seer_engine/{paper,commands}` | 6 | 1 | NORMAL | `.workflows/plan/roster-promotion-pipeline/phase-2.md` | P1-ENG-J5XD | — |
| 3 ✅ | Common-window, risk-adjusted comparison over `equity_snapshots` | R3 | `engine/src/seer_engine/{paper,commands}` | 3 | — | HARD | `.workflows/plan/roster-promotion-pipeline/phase-3.md` | P1-ENG-7V3C | — |
| 4 ✅ | The leaderboard re-sorts honestly, and shows retired horsemen | R3 | `web` | 5 | 1, 3 | NORMAL | `.workflows/plan/roster-promotion-pipeline/phase-4.md` | P1-WEB-C6PK | — |
| 5 ✅ | `promote`: the lab → roster bridge | R4 | `engine/src/seer_engine/{commands,lab}` | 4 | 1, 2 | HARD | `.workflows/plan/roster-promotion-pipeline/phase-5.md` | P1-ENG-Z8MR | — |
| 6 | `FND` onto the roster — the first promotion through the new path | R1 | `engine/src/seer_engine/paper`, `db`, `docs` | 10 | 5 | HARD | `.workflows/plan/roster-promotion-pipeline/phase-6.md` | P1-ENG-H3WF | — |

Four of those cells moved during reconciliation. Phase 1 is 4 files, not 5 (the migration,
`roster.py`, `store.py`, `test_paper_roster.py`). Phase 2 is 6, not 4 (three sources, three test
files). Phase 6 is **10, not 3**, and HARD, not NORMAL: its planner found that
`paper/book.py:decide_book` never calls `prepare_for`, so `FUNDAMENTAL` on the roster would hold
cash forever while every log line said it had decided. `paper/book.py` and `paper/replay.py` are
in no other phase's `Owns`, so phase 6 takes them; that is a real gap the analysis did not reach,
not scope creep, and it serves R1 directly. Phase 3's package widened to include `commands/`,
where its read-only `compare` CLI lives.

Waves the `Depends on` column implies: **{1, 3}** concurrently, then **{2, 4}**, then **{5}**,
then **{6}**.

Phase 3 shares no file with phase 1 — it reads `equity_snapshots`, which `003_paper.sql` already
created, and writes a new module. That independence is real, not optimistic: the comparison math
needs no `status` column, because a strategy's history is comparable whether or not it is still
trading. Phase 4 needs both: phase 3's numbers and phase 1's `status` to label a retired row.

Phase 6 depends on phase 5 rather than on phase 1 alone, deliberately — `FND` is the **proof that
the promotion path works**, so it must travel that path rather than being hand-inserted beside it.

### Phase 1 — The roster becomes data: `status`, `paper_end`, and a name→object resolver

**Satisfies:** R2
**Owns:** `db/migrations/006_roster.sql` *(new)*; `engine/src/seer_engine/paper/roster.py`;
`engine/src/seer_engine/paper/store.py` (read side); `engine/tests/test_paper_roster.py`.
**Does not touch:** `commands/paper.py`'s night logic (phase 2), the comparison math (phase 3),
anything under `web/` (phase 4), `backtest/registry.py` (never).
**Exit criteria:**
- `006_roster.sql` adds **seven** columns to `strategies`, additively: `status text NOT NULL
  DEFAULT 'active' CHECK (status IN ('active','retired'))`, `paper_end date`, `promoted_from text`,
  `object_name text`, `registry_id text`, `gate_note text`, `gate_applicable boolean NOT NULL
  DEFAULT true` — and backfills the four definition columns on the five rows 003/004 inserted.
- `roster.RESOLVER: dict[str, Binding]` maps a stable object name to the live Python object;
  `roster.from_row` / `from_rows` build `RosterEntry` values from database rows through it; and
  `ROSTER` is `from_rows(SEED_ROWS)` — the compiled roster travels the *same* builder as the
  stored one, so the pins prove the data path rather than sitting beside it.
- `store.read_roster_rows(conn)` returns the `engine IS NOT NULL` rows by `(sort, id)`, and
  `roster.from_rows(store.read_roster_rows(conn)) == roster.ROSTER` against a migrated database.
- **The five existing entries resolve to byte-identical `spec_digest` values**, and
  `test_paper_roster.py`'s pinned digests pass unchanged.
- An unresolvable `object_name` raises `UnknownObject` **naming the strategy id and the object
  name**, and poisons the whole build rather than dropping one entry (invariant 9), covered by a
  test.
- `ROSTER`/`ROSTER_IDS`/`MAX_LOOKBACK_BARS`/`entry` keep working for callers that have not moved;
  `MAX_LOOKBACK_BARS` stays 253 and is this phase's alone (see Decisions D12).

### Phase 2 — Retire and activate: the paper night honours roster lifecycle

**Satisfies:** R2
**Owns:** `engine/src/seer_engine/commands/paper.py`; `engine/src/seer_engine/paper/store.py`
(write side); `engine/src/seer_engine/commands/paper_check.py` if the replay needs it;
`engine/tests/test_paper*.py`.
**Does not touch:** `roster.py`'s resolver (phase 1 owns it), the migration (phase 1), `web/`.
**Exit criteria:**
- `commands/paper.py` and `commands/paper_check.py` source their entries from
  `roster.from_rows(store.read_roster_rows(conn))` — **not** from `roster.ROSTER`, and not from
  `read_strategies`, which returns legacy rows `from_rows` correctly refuses.
- `paper` skips `status='retired'` entries: no orders, no equity snapshot, no `paper_state` step.
- Retiring sets `paper_end` to the last session actually traded — at retirement time through
  `store.retire`, or on the next night through `store.set_paper_end` for a retirement taken by
  hand — and never deletes a row.
- A strategy added as `active` with no `paper_start` starts on the next night, exactly as a new
  entry does today (`store.freeze_spec`).
- `store.check_digest`'s `SpecMismatch` refusal is still reachable on every active started
  strategy and `test_changed_frozen_spec_is_refused` still passes, untouched.
- An unresolvable roster entry fails the night with a named error, writes nothing, and its message
  contains neither "retired" nor "skip" — the two skips are never confusable (invariant 9).
- `store.retire` is the only writer phase 5 may use for a retirement; re-retiring is a no-op that
  returns the stored `paper_end`, so an interrupted swap can be re-run.
- `paper_check` replay passes over a window containing a retirement.

### Phase 3 — Common-window, risk-adjusted comparison over `equity_snapshots`

**Satisfies:** R3
**Owns:** `engine/src/seer_engine/paper/compare.py` *(new, pure)*;
`engine/src/seer_engine/commands/compare.py` *(new, the read-only CLI edge)*;
`engine/tests/test_paper_compare.py` *(new)*.
**Does not touch:** the roster, the paper night, `web/`, any schema. It does not read the
`strategies` table at all, which is what keeps it a wave-1 phase with no dependency on phase 1.
**Exit criteria:**
- A pure function takes equity series per strategy and returns, for a stated window: total return,
  CAGR, max drawdown, and a risk-adjusted figure, **plus the window it used and how many sessions
  it covered**.
- **The common window is the intersection** of the compared strategies' live sessions, and it is
  returned explicitly, never implied (invariant 6).
- Inception-to-date is available **separately** and is never mixed into the same ranking.
- A strategy with fewer than `MIN_COMMON_SESSIONS = 63` common sessions is reported as
  `insufficient`, not ranked, and **does not shorten the window for anyone else** — a
  three-week-old method does not win a leaderboard.
- `MIN_COMMON_SESSIONS = 63`, `MIN_RANKED = 2`, annualised Sharpe as the only risk-adjusted
  figure, and `_select`'s drop-the-worst-overlap rule are the **pinned** contract phase 4 ports;
  `as_json` emits exactly the keys in that phase's Interface Contract.
- Pure: no database, no clock, no I/O, in the style of `roster.py` and `compare`'s siblings,
  proved mechanically by an `ast`-based purity test.

### Phase 4 — The leaderboard re-sorts honestly, and shows retired horsemen

**Satisfies:** R3
**Owns:** `web/lib/data.ts` (project `status`, `paper_end`);
`web/app/(app)/leaderboard/{view.ts,page.tsx,leaderboard.module.css}`;
`web/app/(app)/leaderboard/view.test.ts`.
**Does not touch:** engine code, migrations, `web/lib/sera/*`.
**Exit criteria:**
- `bestResearch`'s raw-`totalReturn` max is **deleted** and replaced by a faithful TypeScript port
  of phase 3's `compare` (D10) — same `MIN_COMMON_SESSIONS = 63`, same `MIN_RANKED = 2`, same
  selection rule, same rank key, same statuses — and the window is **shown in the UI**, not just
  computed. No Calmar and no configurable rank key: a knob is a drift vector between two
  implementations that must agree.
- With fewer than 63 shared sessions the page says `No common window yet` and `N of 63 sessions
  shared by every strategy`, and shows **no** "best" figure. That is D8 working, not a regression.
- A retired strategy renders with its history intact and a visible retired marker; it is excluded
  from the window and from "best" without being hidden (D9).
- `looks` handles a roster longer than `CARD_BGS`/`LINES` (4) without two strategies colliding on
  one look, and without assuming exactly four research strategies.
- `web/lib/data.ts` projects `status`, `paper_end` and
  `COALESCE(params->'spec'->>'object', object_name)`, so a just-promoted row is not missing a
  display fact for its first night.
- `npm test` is **+18** on what the phase inherited, and `npm run build` and `npx tsc --noEmit`
  pass.

### Phase 5 — `promote`: the lab → roster bridge

**Satisfies:** R4
**Owns:** `engine/src/seer_engine/commands/promote.py` *(new)*;
`engine/src/seer_engine/lab/store.py` (recording the promotion); its tests.
**Does not touch:** `backtest/registry.py` (D1), the paper night (phase 2 owns it), `web/`.
**Exit criteria:**
- `promote --method M --candidate M-X --id <roster-id> [--retire <id>]` inserts a `strategies` row
  with `status='active'`, `promoted_from='<method id>'`, **the definition columns
  (`object_name`, `registry_id` NULL, `gate_note`, `gate_applicable`)**, full contract-C2
  `params`, and no `paper_start` — so the next paper night starts its clock the ordinary way.
- The row it just wrote is read back and rebuilt through `roster.from_row` **inside the same
  transaction**, so a row the paper night would refuse never commits. That round trip is what
  makes "the roster is data" safe to write from a command.
- It **refuses** to reuse an id that already has a `paper_start` (invariant 3), an allocator the
  resolver does not name (naming the one `Binding(...)` line to add), a method whose variant is
  ambiguous, and a candidate whose rules are not a `sim.rules` preset — each with a named error.
- `--retire <id>` calls `store.retire` (phase 2's, never its own SQL) in the same transaction as
  the insert, so a swap is atomic: the board never shows five active horsemen or three.
- The lab database records the promotion against the method — `analysis` grown, one `insights` row
  — at **any** status, and moves `status` to `paper` only along the `('test-passed','paper')` edge
  `TRANSITIONS` already has. `--lab-status-stays` records without moving, which is the shape a
  `rejected` method needs. `source_sha`, `hypothesis` and `verdict` are untouched and no
  `TRANSITIONS` edge is added.
- A dry-run mode prints every row it would write, in both databases, and writes nothing.
- `backtest/registry.py` is byte-identical to `origin/main` (D1), pinned by a test.

### Phase 6 — `FND` onto the roster: the first promotion through the new path

**Satisfies:** R1
**Owns:** the `FND` `RESOLVER` entry and `SEED_ROWS` row in `paper/roster.py`;
`db/migrations/007_fnd.sql` *(new)*; **`paper/book.py` and `paper/replay.py`'s `MarketAware`
dispatch**; `engine/tests/test_paper_fnd.py` *(new)* plus the widened literals in
`test_paper_book.py`, `test_paper_roster.py`, `test_migrate.py`, `test_paper_check.py`;
the "FND joined the roster" section of `docs/runbooks/paper.md`.
**Does not touch:** `f_fundamental.py`'s own logic, M0005's lab *status*/`source_sha`/`trials`,
`REGISTRY`, `commands/promote.py`, `web/`.
**Exit criteria:**
- `FND` is on the roster as `active`, `sort=6`, `engine='book'`, `rules_id='monthly-hold'`,
  `object_name='FUNDAMENTAL'`, `registry_id IS NULL`, carrying an honest `gate_note` in the style
  of its neighbours — it has **not** passed a gate and must not claim to.
- It is added through phase 5's `promote --method M0005 --candidate M0005-ALL --id FND
  --lab-status-stays`, which also records the promotion in the lab, proving the pipeline rather
  than bypassing it (D7, D11). The documented-equivalent SQL is the escape hatch only.
- `paper.book.decide_book` and `paper.replay.expected_book` dispatch a `MarketAware` allocator
  through `prepare_for` + `targets_prepared`, so `FND` reaches `market.fundamentals` — **without
  this it would hold cash forever while every log line said it decided.** For every allocator that
  is not `MarketAware` the expression is byte-identical to today's, so the five existing
  strategies replay bit for bit.
- The paper night produces orders or an explicit empty decision for `FND` against a `Market`
  carrying the fundamental panel, and `paper_check` replays it as `ok`, never `mismatch`.
- **A `Market` with no panel yields no trades, not wrong trades** — `f_fundamental`'s documented
  empty-panel behaviour is asserted by a test at the roster level.
- `roster.FUNDAMENTAL_PARAMS` equals M0005's `COMPOSITE` by value, pinned by a test: `roster.py`
  must never import a lab method, and only that equality keeps the promoted row's frozen digest
  and the roster's recomputed digest the same.
- The five pre-existing `spec_digest` values are byte-identical, and `MAX_LOOKBACK_BARS` is still
  253 (`FND`'s lookback is 20).
- Nothing claims `FND` passed a backtest gate, and the go-live checklist's arithmetic still reads
  honestly with a fifth research strategy present (`CHECKS = 6` is per strategy; checked).

## Reconciliation Log

Round 1. The six planners ran concurrently, and phases 4, 5 and 6 were written before the plans
they declared a dependency on existed — so every cross-phase name in them was a guess. Most were
wrong. Each row below was fixed by **editing the losing side out of the plan file**, not by noting
it; nothing here is left for a phase session to discover at 3am.

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | Phase 2 called `roster.for_rows(rows)` at `commands/paper.py:execute` and `commands/paper_check.py:check`. Phase 1 defines `roster.from_rows`. | Unmet assumption | Phase 2's four call sites, its Requires list and its docstring rewritten to `from_rows`. Phase 1 owns `roster.py`; its name stands. |
| 2 | Phase 2 passed `store.read_strategies(conn)` to the builder. That returns legacy display rows with `engine IS NULL`, which phase 1's `from_row` correctly refuses with `BadRosterRow` — so the first night would have failed. | Broken-build phase | Phase 2 now calls `store.read_roster_rows(conn)` (phase 1's `engine IS NOT NULL` query) in both `paper.py` and `paper_check.py`. |
| 3 | **The resolver-key location** — phase 2's highest-risk assumption. Its `make_unresolvable` helper broke `params->'spec'->>'object'`, which is NULL on an unfrozen row, and it warned this would fail `test_paper_command.py:243` / `test_paper_check.py:170` if the key lived only in the spec. | Unmet assumption — **and it was already right** | Phase 1 put the key in its own column, `strategies.object_name`, backfilled by 006. No bug. Phase 2's helper rewritten to `UPDATE strategies SET object_name = 'NO_SUCH_OBJECT'`, and its Requires item rewritten from a warning into the settled fact. |
| 4 | Phase 2's test asserts the unresolvable-entry error contains the strategy id. Phase 1's `UnknownObject` message named only the bad value. | Contract drift | Phase 1's `from_row` now re-raises `UnknownObject` and `UnknownRules` prefixed with the row id, and its docstring says every `RosterError` names the row. Invariant 9 means *which* portfolio stopped the night, not just that one did. |
| 5 | `roster.MAX_LOOKBACK_BARS` was handed off by phase 2 to "phase 1 / phase 6" — owned by neither. | Gap | Assigned to **phase 1**, unchanged, with the reasoning written into `roster.py`'s docstring: it is a property of `SEED_ROWS`, no production path reads it, and the live guard is phase 5's `promote.check_lookback`. Recorded as D12. Phase 2's and phase 6's handoffs rewritten to say it is settled. |
| 6 | **`MIN_COMMON_SESSIONS`: phase 3 said 63, phase 4 said 21.** | Contract drift (the silent-divergence kind) | 63, on the phases' exit criteria — phase 3 pins the number by name, phase 4 names none. Phase 4's constant, every fixture in its 20 new tests, its window-line copy, its A3 table, its A5 note and its manual check all rewritten from 25-session to 63-session curves. Recorded as D8. |
| 7 | Phase 4's port added a `RANK_BY` knob and a `calmar` figure phase 3 does not have, and its rank key omitted phase 3's max-drawdown tiebreak. | Contract drift | `RANK_BY` and `calmar` **deleted** from phase 4; `rankCmp` rewritten as phase 3's `_rank_key`. A configurable rank key is exactly how a port and its reference drift apart. |
| 8 | Phase 4's selection ("intersect the seasoned") is not phase 3's `_select` (greedy drop of the worst-overlapping strategy). On a board where one strategy barely overlaps, the CLI would rank three strategies and the leaderboard would rank none. | Contract drift | Phase 4's `compare` rewritten around a ported `selectRanked`, with `MIN_RANKED = 2`, plus a test (`drops the worst-overlapping strategy rather than ranking nothing`) that pins the case. |
| 9 | Phase 3 guarantees `window === null` ⟺ nothing ranked; phase 4's `windowLine` read `window.sessions` to say how short the board still is, which would have printed `0 of 63` forever. | Contract drift | Phase 4's `Comparison` gains a `shared` field — presentation only, never ranked — and `windowLine` reads it. Phase 3's guarantee is preserved exactly. |
| 10 | **Retired strategies in the ranking.** Phase 3's module ranks any curve handed to it and its handoff implied a retired strategy is ranked; phase 4 excludes them from the window entirely. | Behavioural fork | Settled on the index's own phase-4 exit criterion (*"excluded from 'best'"*): **the caller excludes, the math stays status-blind.** Phase 3's handoff rewritten to say so and its `--exclude` help text now names the use; phase 4's pre-filter documented as a third, UI-only status. `compare.py` keeps its zero dependency on phase 1, which is what makes it a wave-1 phase. Recorded as D9. |
| 11 | Phase 4 and phase 3 both chose "port, not call", independently and for the same reason. | Agreement worth recording | Confirmed and recorded as D10 so no later session re-opens it. Phase 4's header comment now states the obligation in both directions. |
| 12 | **Phase 5's `promote` INSERT omitted `object_name`, `registry_id`, `gate_note` and `gate_applicable`.** Every promoted row would have been unbuildable, and `roster.from_rows` would have failed **the whole night for the whole board** on the first run after a promotion. | Deleted-then-used / broken build — the worst one in the set | `_insert` rewritten to write all four; `render_plan` prints them; and the row is read back and rebuilt through `roster.from_row` inside the transaction before it commits, so a row the night would refuse never lands. A new test pins the round trip. |
| 13 | Phase 5 read `roster.RESOLVER` as `Mapping[str, object]`. Phase 1 defines `dict[str, Binding]`. | Unmet assumption | `object_name_of` rewritten to scan `b.obj is obj`; its "add one line" refusal now quotes a `Binding(...)`; the inverse-lookup test rewritten. |
| 14 | Phase 5 claimed `store.retire` raises on an already-retired row. Phase 2 makes it a no-op returning the stored `paper_end`, deliberately, so an interrupted swap can be re-run. | Contract drift | Phase 5's Requires corrected to phase 2's actual contract. Phase 2 owns the function. |
| 15 | **No lab method's allocator is in phase 1's `RESOLVER`** (M0001/M0004 use the lab-local `OWNVOL`, M0005 uses `FUNDAMENTAL`), so every happy-path test in phase 5 would have hit its own `NotPromotable`. | Broken-build phase | Phase 5's test module gains an autouse fixture that borrows the `FUNDAMENTAL` binding for the test's duration, documented as the real state of the tree, plus a test that turns it off to prove the refusal. Phase 6 commits the real line. This is D2's cost, now said out loud in three places. |
| 16 | A lab candidate whose `rules` is not the `sim.rules` preset of its id would be frozen under one rule set and read back under another — a `SpecMismatch` surfacing on a paper night. Noticed during reconciliation; owned by nobody. | Gap | New `promote._check_rules` refusal in phase 5, called from `build_promotion`, with a test. |
| 17 | **Phase 6 required a `--no-lab-record` flag phase 5 does not ship**, on the premise that the lab cannot record a promotion of a `rejected` method. | Unmet assumption built on a false premise | The premise is wrong: `analysis` only grows and `insights` is append-only, so `record_promotion` writes at **any** status; only the status *move* is blocked, and `--lab-status-stays` is the flag for that. Phase 6 rewritten to use it. Strictly better — FND's promotion is now recorded in both databases, which is what D7 was for. Recorded as D11. |
| 18 | Phase 6 appended a sixth `RosterEntry` literal to `ROSTER`, which phase 1 replaced with `from_rows(SEED_ROWS)`. Its "adaptation note" offered three mutually exclusive shapes. | File collision / unresolved fork | Step 3 rewritten to phase 1's one shape: one `RESOLVER` entry (a `Binding`), one `RosterRow` in `SEED_ROWS`. The adaptation note is **deleted** — leaving three options in a plan is leaving the fork for the session. |
| 19 | Phase 6's `007_fnd.sql` wrote display columns only, so a freshly migrated database would hold an `FND` row `roster.from_row` refuses, failing both phase 1's migration-equality test and every CI paper test. | Deleted-then-used | 007 rewritten to carry `object_name`, `registry_id`, `gate_note`, `gate_applicable` and `promoted_from`, byte-for-byte the seed row, with the definition columns kept out of the `DO UPDATE` list only where `promote` owns them. |
| 20 | Phase 6's `promote` invocation omitted `--candidate`; M0005 has six variants and phase 5 refuses to guess. Phase 6 also asserted `promoted_from` must be NULL, which contradicts phase 5's insert and D7. | Contract drift | Command corrected to `--candidate M0005-ALL --lab-status-stays`; `promoted_from='M0005'` throughout, with the runbook text rewritten to explain why that asserts no lab transition. `M0005-ALL`'s params were verified against the method file: `FundamentalParams(rank="composite", top=20)`, exactly phase 6's `FUNDAMENTAL_PARAMS`. Recorded as D13. |
| 21 | `roster.FUNDAMENTAL_PARAMS` and the lab's `COMPOSITE` are deliberately separate objects (roster must not import a lab method). Nothing stopped them drifting, and a drift would fail FND's **second** night with a `SpecMismatch`, not its first. | Gap | New test in phase 6 pinning value equality, with the reasoning in the plan and in `roster.py`'s comment. |
| 22 | **Migration numbering.** Phase 1 writes `006_roster.sql`, phase 6 writes `007_fnd.sql`. | Checked, no conflict | No collision: 006 adds columns and backfills five rows; 007 inserts one new row and names no column 006 did not create. Both are `ADD COLUMN IF NOT EXISTS` / `INSERT … ON CONFLICT`, nothing dropped, no CHECK narrowed, 001–005 untouched. Invariant 5 holds. Stated explicitly in 007's impact note. |
| 23 | Phase 4's `data.ts` projected `params->'spec'->>'object'`, NULL on a row `promote` just wrote, so a promoted strategy loses a display fact for its first night. Flagged by phase 1, owned by nobody. | Gap | Assigned to phase 4 as a one-line `COALESCE(params->'spec'->>'object', object_name)`. |
| 24 | **Test deltas** were a mix of absolutes and stale counts. | Contract drift | All six restated as per-phase deltas off what the phase inherits, and recomputed after the edits: see the table below. |
| 25 | Phase 6 declared 10 files against the index's 3, and flagged it. | Scope, correctly flagged | **Accepted.** `paper/book.py`'s missing `MarketAware` dispatch is a real gap the analysis did not reach, it serves R1 directly, and no other phase owns those files. Phase table updated to 10 files and HARD. |

**Test deltas, reconciled.** Each is off what the phase inherits, never an absolute (invariant 1):

| Phase | with `PG_TEST_URL` | without |
|---|---|---|
| 1 | +15 passed | +12 passed, +3 skipped |
| 2 | +11 passed | +0 passed, +11 skipped |
| 3 | +35 passed | +32 passed, +3 skipped |
| 4 | engine 0; **web +18** | same |
| 5 | +24 passed | +14 passed, +10 skipped |
| 6 | +16 passed | +16 passed |

Arithmetic for the fully merged branch, given the measured baseline at `0d03490` of
**2261 passed / 332 skipped** and **2593 passed / 0 skipped** with `PG_TEST_URL`:

- with `PG_TEST_URL`: `2593 + 15 + 11 + 35 + 24 + 16` = **2694 passed, 0 skipped**
- without: `2261 + 12 + 0 + 32 + 14 + 16` = **2335 passed**, and `332 + 3 + 11 + 3 + 10` =
  **359 skipped** (2694 total either way, which is the check)
- `web`: `247 + 18` = **265 passed, 24 files**

That is arithmetic for a reader, **not a gate.** No phase should compare against it; each reports
its own delta off what it inherited, because the phases land in a swarm and in any order the
dependency graph allows.

## Decisions

| # | The fork | The choice | The rung |
|---|---|---|---|
| D1 | Promote into `backtest.registry.REGISTRY` (how F1/F4 reach the roster today) or give promoted methods their own resolver path | **Own resolver path. `REGISTRY` is never appended to.** | **Surrounding code** — `registry.py:3` says `REGISTRY` is *"every strategy the P7a dev run tries, fixed BEFORE the run"*, `:12` caps it at `dev.MAX_CANDIDATES` (60), and `candidate_digest` is pinned in `tests/test_registry.py`. Appending would corrupt the multiple-testing count the lab's `trials` table (`UNIQUE(config_digest, window)`) exists to maintain |
| D2 | Make the roster fully data (object reference included) or keep a code-side resolver | **A code-side resolver keyed by a stable name; everything else is data.** | **A stated invariant** — invariant 2 requires `spec_digest` byte-stability, and the spec includes the object's module-level name and its `id`. A database cannot hold a live `Allocator`, and `eval`-ing a path from a database row would make the roster a code-execution surface. The resolver is the smallest thing that must stay in code |
| D3 | Replacing a horseman: edit the row, or insert-new + retire-old | **Insert new, retire old, in one transaction.** | **A stated invariant** — invariant 3, which is `roster.py`'s own documented rule (*"a changed strategy needs a new id with its own paper clock, never an edited entry"*) already enforced by `store.check_digest`. Editing in place would show months of track record that belonged to a different algorithm |
| D4 | Rank on raw total return (today's `bestResearch`) or on a common window | **Common window, stated explicitly, with inception-to-date kept separate.** | **The user's raw input** — *"a robust pipeline to easily compare and 're-sort'"*. Raw total return across unequal windows measures the market, not the method, so it cannot serve R3. Promoted to invariant 6 |
| D5 | Does `FND` need to pass a gate before joining the roster? | **No.** It joins with an honest `gate_note` saying it has not passed, exactly as A, F4 and F1 do | **The user's raw input** — *"this is just a paper trading app. we clearly agrees that i won't use real money until we pass all gates"*, corroborated by **surrounding code**: all four non-benchmark entries carry `failed` or `not applicable` gate notes today |
| D6 | Should promotion be automatic when a Sera session finds a better method? | **No. Every promotion is a human-invoked command in this set.** | **The user's raw input** — *"we should be able to easily 'promote' it"* asks for the capability, not for autonomy. An auto-promoting pipeline writing to the live leaderboard is a separate decision with a different risk profile, and nothing here needs it to be true |
| D7 | Phase 6 inserts `FND` directly, or through phase 5's `promote` | **Through `promote`.** | **The index's Why** — R4 is the deliverable and `FND` is the only promotion available to prove it. A hand-inserted row would leave the pipeline shipped but never exercised |

D1–D7 were written before the phase plans existed. **Reconciliation proved none of them wrong.**
D2 was tested hardest — phase 5 found that *no* committed lab allocator is in the resolver, so
every promotion available today costs exactly one `RESOLVER` line — and that is D2's stated price,
paid, not a counter-example. D7 was strengthened: phase 6 had planned to skip the lab half of the
promotion, and now travels all of it. The rows below were settled during reconciliation.

| # | The fork | The choice | The rung |
|---|---|---|---|
| D8 | `MIN_COMMON_SESSIONS`: phase 3's **63** or phase 4's **21** | **63**, in both implementations. The leaderboard therefore shows no "best" until the paper record reaches 63 shared sessions, and says `N of 63 sessions shared` instead | **The phases' exit criteria** — phase 3's exit criterion 3 pins the number *by name* (`MIN_COMMON_SESSIONS = 63`) and defends it (one quarter of a trading year; three full rebalances for a `monthly-hold` book, so a ranked strategy has made three independent decisions inside the window). Phase 4's exit criteria name no number, and its own A3 offered the constant as the thing to change. The visible cost — a quiet leaderboard for a quarter — is invariant 6 being obeyed, not a regression |
| D9 | Does a **retired** strategy enter the ranking? Phase 3's module ranks any curve it is given; phase 4 excludes them | **Excluded — by the caller, not by the math.** `compare.py` stays status-blind; phase 4 filters before computing the window, and `compare --exclude <id>` is the same filter for a human | **The phases' exit criteria** — the index's phase-4 criterion already said a retired strategy *"is excluded from 'best' without being hidden"*. Putting the rule in `compare.py` would have given a pure math module a dependency on phase 1's `status` column and cost it its wave-1 independence; putting it in the caller costs nothing and keeps both halves honest |
| D10 | Phase 4 **calls** phase 3's CLI or **ports** its math to TypeScript | **Ports.** `compare.py` is the reference implementation and its tests are the specification; `--json` exists so the port's fixtures can be pinned against it | **Surrounding code** — `backtest/metrics.py:1` says it *"ports `strategyMetrics` and `checklist` line for line"* from `web/lib/metrics.ts`, so crossing this boundary by porting is already the house pattern. And the leaderboard is a `force-dynamic` server component rendering inside a request against Neon: there is no Python runtime in the Vercel function to call. Both planners reached this independently; it is recorded so no later session re-opens it |
| D11 | `FND`'s lab record: **skip it** (phase 6's `--no-lab-record`) or **write it without moving the status** (phase 5's `--lab-status-stays`) | **Write it.** `promote` appends a `# Promotion` section to `methods.analysis` and one `insights` row, and leaves `M0005` at `rejected` | **The plans' code blocks** — phase 5 read `lab/store.py` and measured that `methods_analysis_grows` permits growth and `insights` refuses only UPDATE and DELETE, so both writes are legal at *any* status; `rejected` being terminal blocks only the status move. Phase 6's premise ("the lab refuses the record") was simply false. Corroborated by **the index's Why**: R4's deliverable is a pipeline, and a promotion no one can find from the lab end is a pipeline that half ran |
| D12 | `roster.MAX_LOOKBACK_BARS` over the compiled tuple, over the **active** entries, or over the live database rows | **Over the seeded roster, unchanged, owned by phase 1.** It stays `max(e.lookback for e in ROSTER)` and stays 253 | **The plans' code blocks** — no production path reads it: `commands/paper.py:_check_window` recomputes the max over the entries that trade tonight, and its only consumers are two assertions in `test_paper_roster.py`. The live guard against admitting a strategy the night's bar window cannot feed is phase 5's `promote.check_lookback`, which runs at promotion time against `store.MARKET_WINDOW_DAYS`. Phase 2 and phase 6 each handed this to "someone else"; it is now one phase's, and it does not change |
| D13 | `FND`'s engine, rules and parameters — phase 6 chose `book` / `monthly-hold` / composite-top-20, phase 2's night and phase 1's resolver had to agree | **`engine='book'`, `rules_id='monthly-hold'`, `FundamentalParams(rank="composite", top=20)`, promoted from variant `M0005-ALL`** | **The plans' code blocks**, verified against the tree: `m0005_fundamental_factors.py:52` builds every candidate with `rules=MONTHLY_HOLD, allocator=FUNDAMENTAL`, and `MONTHLY_HOLD.engine == "book"`, so phase 5's `promote` — which takes the triple off the `Candidate` unchanged and forbids a `--params` override — cannot write anything else. `M0005-ALL` is `COMPOSITE`, the a-priori four-factor blend, **not** the best-performing variant (`M0005-VAL`): choosing on the dev-window numbers is choosing on the multiple-testing noise the lab's `trials` table exists to count |

## Open Questions

**None.**

Every fork was decidable from the ladder and was decided — the six settled during reconciliation
are D8–D13, each with its rung named. Every requirement id has at least one phase serving it, so
nothing is parked here for lack of an owner either.

Nothing in this set is irreversible, which is the test for whether an item belongs here at all:
no method id is spent, no `trials` row is recorded, `REGISTRY` is untouched, both migrations are
additive, no paper clock is reset, no history row is deleted, and `main` is not written to until
the set is merged. The two writes that cannot be *deleted* — phase 5's appended lab `analysis`
section and `insights` row, because the lab is append-only by trigger — are rolled back by
`git checkout -- lab/lab.sqlite web/data/lab.json`, which is why that database is committed. The
one externally visible change, a fifth research strategy on `seertrade.site/leaderboard`, is
reversed by setting its `status` to `retired`.

## Rollback

**Per phase.** Every phase is one commit on `feature/roster-promotion-pipeline`; `git revert`
backs it out. The phases with effects outside git:

- **Phase 1 and 6** add migrations. Both are additive (`ADD COLUMN IF NOT EXISTS`, new rows), so
  rolling back the code leaves harmless unused columns. To undo the data:
  `UPDATE strategies SET status='active', paper_end=NULL, promoted_from=NULL`, and
  `DELETE FROM strategies WHERE id='FND'` **only while `FND` has no `paper_start`** — once it has
  traded a night, retire it instead (`status='retired'`), because deleting it would destroy the
  record invariant 4 protects.
- **Phases 5 and 6** write to the committed `lab/lab.sqlite` (phase 5 ships the code; phase 6 is
  the first run that actually writes it, recording `FND`'s promotion against `M0005`). The lab is
  append-only by trigger, so the appended `analysis` section and `insights` row cannot be
  deleted — they are rolled back by `git checkout -- lab/lab.sqlite web/data/lab.json`, which is
  why the file is committed in the first place. Do it before any other lab write lands on top.
  `M0005`'s status, `source_sha`, `hypothesis`, `verdict` and six `trials` rows are never written,
  so nothing else in the lab needs undoing.
- **Phase 2** changes which strategies trade on a night. A wrong retirement is undone by setting
  `status='active'` and clearing `paper_end`; the strategy resumes on the next night with its
  history intact, because nothing was deleted.

**As a whole.** `git branch -D feature/roster-promotion-pipeline` and
`git worktree remove /home/miftah/.worktrees/seer/roster-promotion-pipeline`. On the database,
the three `UPDATE`/`DELETE` statements above. Production is unaffected until the set is merged
and a paper night runs.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f ROSTER_PROMOTION_PIPELINE_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f ROSTER_PROMOTION_PIPELINE_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan ROSTER_PROMOTION_PIPELINE_PLAN.md

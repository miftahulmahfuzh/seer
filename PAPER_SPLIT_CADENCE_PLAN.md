# Plan: Nightly paper trading for split-cadence rules (monthly pick, weekly resize)

**Slug:** paper-split-cadence
**Date:** 2026-10-07 01:19 (WIB)
**Analysis:** `20261007-011957-S9C4_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/paper-split-cadence`
**Branch:** `feature/paper-split-cadence` (base: `origin/main` @ `dffac31`)
**Phases:** 3
**Status:** planned
**Coordinator:** —

---

## Why

From `docs/handover/2026-10-07-paper-split-cadence.md` §0, verbatim:

> Some lab methods pick their stocks once a month but re-check how much to hold every week. The
> backtest engine already runs them. The nightly paper engine refuses them, on purpose, because it
> does not remember last month's basket between nights. The owner has said a weekly check is fine
> if it performs better (2026-10-07), and lab method M0022 (RM's book with its volatility brake read
> weekly) is the first candidate that needs this. If M0022, or any later method on a split-cadence
> rule set, passes the lab and gets promoted, the paper night must be able to run it. This handover
> is that missing feature, built before it is needed, so a promotion is never blocked on it.
>
> Nothing here changes what any current roster strategy does. Every roster entry today
> (`SPY`, `A`, `C`, `F4-MOM12-N20-TREND-FR`, `F1-SPY-SMA200-M-FR`, `RM-FR`) uses rules without a
> `resize_cadence`, and their decisions, records and digests must stay byte for byte.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | `decide_book` accepts split-cadence rules: on a resize-only session it returns exactly `run_book`'s `_with_idle(_rescaled(...))` given the last rank basket and the book's marks; stays pure; rank sessions unchanged | 1, 2 |
| R2 | The last rank basket is persisted, not recomputed — read back from `book_targets` (option a) | 2 |
| R3 | Replay agrees: `paper_check` green over many nights incl. a resize week, a mid-month kickoff, a split inside the month, a stopped-out position not re-bought | 1, 2 |
| R4 | Existing strategies untouched (records, replays, `PINS`); backtest code is a closed record | 1, 2, 3 |
| R5 | `MONTHLY_RANK_WEEKLY_RESIZE_FRAC` appended to `PRESETS`; `promote --fractional` maps to it | 1 |
| R6 | Positions page: plain words "picks monthly, adjusts weekly"; on a resize week shows what to trim or top up | 3 |
| R7 | Promote accepts only what paper runs and paper runs all it accepts; a test promotes a split-cadence candidate into a test DB and runs nights | 2 |

## Scope

**In scope:** `sim/rules.py` new preset; `paper/book.py` (`decide_book` split path, `needs_kickoff`,
pure last-rank helpers); `paper/replay.py` decisions loop; `commands/paper.py` wiring; tests; the
Positions page copy and a trim/top-up cell for split-cadence strategies.

**Out of scope:** `backtest/book_runner.py`, `sim/book.py`, `sim/rules.py` session functions and
`RESIZE_BAND` (closed record); any migration; a fractional twin for `MONTHLY_RANK_WEEKLY_RESIZE_TBILL`
(not asked for; `fractional_twin` keeps refusing it with its existing message); promoting M0022
(it was rejected by the lab); the leaderboard and any other page.

## Invariants

1. The tree builds and the full verification passes at the end of every phase:
   `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
   (only the two known Python-3.12-only failures allowed), `engine/.venv/bin/ruff check engine`,
   and for phase 3 `cd web && npx vitest run && npx tsc --noEmit`. The worktree needs its own
   `engine/.venv` (`python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`)
   and `web/node_modules` (`cd web && npm ci`); main's venv tests the wrong tree.
2. For every rule set with `resize_cadence is None`, `decide_book`, `needs_kickoff`,
   `expected_book` and the paper night behave byte for byte as on `dffac31`.
   `tests/test_paper_roster.py::PINS` is not edited.
3. `backtest/book_runner.py` and `sim/*` behaviour do not change; `_rescaled` and `_with_idle` are
   imported, never copied.
4. `paper/book.py` and `paper/replay.py` stay pure (purity test).
5. No migration; `book_targets` is the only store of the last rank basket.
6. Site text is plain words, no ids/codes; any new button is icon-only Lucide with `aria-label` and tooltip.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Pure split-cadence decision, replay and fractional preset | R1, R3, R5 | `engine/paper`, `engine/sim` | 9 | — | HARD | `.workflows/plan/paper-split-cadence/phase-1.md` | — | — |
| 2 | Nightly wiring and end-to-end tests (paper night, paper_check, promote) | R1, R2, R3, R7 | `engine/commands`, `engine/tests` | 2 | 1 | HARD | `.workflows/plan/paper-split-cadence/phase-2.md` | — | — |
| 3 | Positions page: monthly pick / weekly size copy and buy/add/trim cell | R6 | `web` | 4 | — | NORMAL | `.workflows/plan/paper-split-cadence/phase-3.md` | — | — |

### Phase 1 — Pure split-cadence decision, replay and fractional preset
**Satisfies:** R1, R3, R5 (holds R4)
**Owns:** `sim/rules.py` + `sim/__init__.py` (`MONTHLY_RANK_WEEKLY_RESIZE_FRAC`, appended last to
`PRESETS`, exported); `paper/book.py` (`decide_book(..., *, force=False, last_rank=None, marks=None)`,
removal of the refusal, `needs_kickoff` on `is_rank_session`, new pure helpers
`last_rank_session(rules, paper_start, kickoff, session)` and `rank_basket(targets, idle_symbol)`);
`paper/replay.py` (`expected_book` decisions loop tracks the expected last rank basket and the
replay's marks); unit tests in `test_paper_book.py` (replace the refusal test), `test_paper_kickoff.py`,
`test_sim_rules.py` (preset id list), `test_promote_command.py` (twin), `test_paper_replay.py`.
**Does not touch:** `commands/paper.py`, `paper/store.py`, web.
**Exit criteria:** looping `decide_book`/`settle_book` night by night over a split-cadence rule set,
with `last_rank` from `rank_basket` of the previous rank decision, reproduces `run_book` field for
field (resize weeks, a mid-month kickoff, a stopped-out position not re-bought, idle instrument);
`expected_book` gives decisions equal to that loop; `fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE)`
is the new preset; full engine suite green.

### Phase 2 — Nightly wiring and end-to-end tests
**Satisfies:** R1, R2, R3, R7 (holds R4)
**Owns:** `commands/paper.py` only among sources: private `_resize_only(rules, session, kickoff)`
and `_split_inputs(conn, strategy_id, rules, paper_start, kickoff, session, positions)`; `_start`
and `_step_book` pass, for split rules only, `last_rank` = `rank_basket(store.read_book_targets(...
last_rank_session(rules, paper_start, kicked, nxt)))` (None when no rank yet, `()` when the rank
stored no rows) and `marks` = the settled book's `{symbol: mark}`; `kicked` is the stored kickoff,
updated in-loop after a kickoff write; evidence `None` on a resize-only decision (a forced kickoff
keeps evidence); rules without `resize_cadence` call `decide_book` exactly as today. New
`engine/tests/test_paper_split_cadence.py`: a scripted `monthly-rank-weekly-resize-frac` entry over
20 Postgres nights (kickoff Wed 2026-10-14, resize weeks, a catch-up night across the November rank,
a 2:1 split on a held symbol on a resize Monday, a stopped-out position never re-bought) equal to
`run_rules`, `paper_check` `ok` / `split-affected`, never `mismatch`; and `promote --fractional` of
lab variant `M0022-W-TV14` into the test DB (its `RESOLVER`/`EVIDENCE` entries via `monkeypatch`
only), then 25 nights to a green `paper_check`.
**Does not touch:** `paper/book.py`, `paper/replay.py`, `paper/store.py` (no `read_rank_basket`
helper: `read_book_targets` + `rank_basket` suffice), `commands/promote.py`, any existing test file
(`test_paper_book.py`, `test_paper_replay.py` are phase 1's), web; no committed `RESOLVER`/`EVIDENCE`
entry for M0022, no `RM-FR` roster change, no `PAPER_PAUSED` change (see On Landing).
**Exit criteria:** the split-cadence roster entry paper-trades end to end with stored snapshots,
fills, positions and decisions equal to `run_rules`/`run_book`; resize-only decisions carry no
evidence; `promote --fractional` writes `rules_id = 'monthly-rank-weekly-resize-frac'` and trades to
a green `paper_check`; every existing test unedited and green.

### Phase 3 — Positions page copy and trim-or-add cell
**Satisfies:** R6 (holds R4)
**Owns:** new `web/lib/cadence.ts` (`SPLIT_CADENCE_RULES` = `monthly-rank-weekly-resize`,
`monthly-rank-weekly-resize-tbill`, `monthly-rank-weekly-resize-frac`; `picksMonthlySizesWeekly`,
`RESIZE_BAND = 0.01`, `sizeChange`, `heldUsd`, `orderSizeChange`, `sizeLabel`, `sizeTip`) and
`web/lib/cadence.test.ts`; in `web/app/(app)/positions/page.tsx` the three monthly sentences (158,
166, 374) branching on it, and for such a strategy a full-width per-order `SizeCell` comparing the
target dollars (weight × equity) with what is held now: "Buy about $X" (symbol not held — the band
does not apply), "Add about $X", "Trim about $X", or "No change" when the gap is under 1% of equity
(the engine's `RESIZE_BAND`), each with a plain-words tooltip; `.cellWide` in
`positions.module.css`.
**Does not touch:** engine; `web/lib/data.ts`; any existing strategy's rendered text.
**Exit criteria:** non-split strategies render exactly as before; for a split-cadence strategy the
sentences speak of a monthly pick and a weekly size check and each book order shows Buy / Add /
Trim about $X or No change; vitest and tsc green.

## Reconciliation Log

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | Phase 1 Step 6 replaced `test_paper_book.py:25-52`, but `:52` is `_ZERO = Decimal("0.0000")`, which phase 1's own `split_paper_run` uses; the range would delete it and break the test module | Broken-build phase / contract drift | phase-1.md: range corrected to `:25-50` (through the `f_index` import) in the Files table and Step 6, with an explicit note that `_ZERO` stays |
| 2 | Phase 2's Requires said `needs_kickoff` on `is_rank_session` means "a clock never kicks off on a resize-only session"; phase 1 (and the Decisions row) say the opposite: it kicks off there | Contract drift | phase-2.md Requires rewritten to phase 1's semantics; it also notes that such a kickoff is a forced rank, so `_resize_only` is False and it keeps evidence (phase 2's code already did this) |
| 3 | Phase 2's statement of `decide_book`'s contract omitted the resize path's argument rules (marks required → ValueError; `last_rank` must be a tuple → TypeError on a list; marks a `Mapping[str, Decimal]`) | Unmet assumption (unstated) | phase-2.md Requires now quotes phase 1's contract exactly; phase 2's code already passes `rank_basket(...)` (a tuple) or None and a `dict` of marks |
| 4 | Which kickoff `_split_inputs` sees for a session decided later in the same catch-up night as the kickoff | Contract drift (ambiguous wording) | phase-2.md Requires and Step 5 Impact, and phase-1.md Handoffs, now state it: `kicked` starts at `state.kickoff_session` and is set to `nxt` right after `write_kickoff`, as `split_paper_run` updates `kickoff`; phase 2's code already did this |
| 5 | "No rows" vs "no rank" for the last rank basket | Contract drift (wording) | phase-2.md Requires now says it: no rank session → `last_rank_session` None → `last_rank` None; a rank that stored no rows → `read_book_targets` `()` → `rank_basket` `()` (verified: `store.read_book_targets` returns `()` for no rows) |
| 6 | Phase 2 hedged on where `MONTHLY_RANK_WEEKLY_RESIZE_FRAC` is importable from | Contract drift | phase-2.md note fixed: defined in `sim.rules`, re-exported from `sim` (phase 1 Steps 1–2) |
| 7 | Phase 1 Handoffs invited phase 2 to import `split_market`/`BREATHE`/`split_paper_run` from `test_paper_book.py`; phase 2 builds its own Postgres world and imports none | Duplicate work / file collision (potential) | No collision: phase 2 creates only `test_paper_split_cadence.py` and edits no existing test file. phase-1.md Handoff updated to say so; `test_paper_book.py`, `test_paper_kickoff.py`, `test_paper_replay.py`, `test_sim_rules.py`, `test_promote_command.py` are phase 1's alone |
| 8 | Index phase 2 Owns offered an optional `store.read_rank_basket`; phase 2 rejected it | Contract drift (index vs plan) | Index phase 2 section rewritten to the plan: `paper/store.py` untouched; file count 2 |
| 9 | The promote end-to-end test uses lab variant `M0022-W-TV14`, which needs `RESOLVER`/`EVIDENCE` entries the On Landing section forbids committing | Scope guard | Confirmed test-only (`monkeypatch.setitem`); phase-2.md implementer notes and the index phase 2 "Does not touch" now say explicitly: no committed RESOLVER/EVIDENCE for M0022, no RM-FR roster change, no `PAPER_PAUSED` change |
| 10 | Index phase 3 described "Add / Trim / No change" only; phase 3 also labels an unheld symbol "Buy about $X" and creates `web/lib/cadence.ts` | Contract drift (index vs plan) | Index phase 3 section and phase-table title rewritten to the plan (Buy / Add / Trim / No change, file list); Decision row added |
| 11 | Phase 3's split-cadence id set vs phase 1's preset id | Check | Equal (`monthly-rank-weekly-resize-frac`); phase-3.md Handoff marked confirmed |

Ledger after edits: phase 1 creates `decide_book(…, last_rank, marks)`, `last_rank_session`,
`rank_basket`, the preset, and deletes only the refusal + its test (no later phase references
either); phase 2 consumes those and deletes nothing; phase 3 is independent. Every dependency
points backward; no file is touched by two phases; every impact point (1–7) and every R has an
owner; each phase builds green on its own (phase 1 leaves `commands/paper.py` valid, since it
passes neither new keyword).

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Last rank basket: (a) read back from `book_targets` or (b) new column/table | (a). Exact: `_rescaled` reads only `symbol` and `weight` of `last_rank` (its `t.last` fallback is unreachable: kept symbols are all held, so all in `marks`); `apply_book_split` leaves weight unchanged; stored weights are exact at `WEIGHT_QUANTUM`; idle is always the trailing row. No split-adjusting is needed. | 5: user raw input ("prefer (a) if it is exact") + analysis proof |
| How the last rank session is found (an empty rank basket writes no rows) | From the calendar, not from rows: latest `d` in `[paper_start, session)` with `is_rank_session(rules, d)` or `d == kickoff_session`; rows at `d` minus a trailing idle row are the basket (`()` when none); `None` only when no such `d` | 6: surrounding convention (`run_book`'s `rank = is_rank_session or session == kickoff`) |
| A clock that starts on a resize-only Monday | `needs_kickoff` tests `is_rank_session` instead of `is_decision_session`, so it kicks off that Monday (identical for every rule set without `resize_cadence`, where the two are equal) | 1: invariant 2 + `run_book` kickoff semantics |
| Evidence on a resize-only night (§5 Q1) | None: a resize-only decision stores `evidence=None` (no position is opened); rank and kickoff decisions keep today's evidence | 5: user raw input §5 ("probably no new evidence; confirm") |
| What Explain writes for a resize-only order (§5 Q4) | Nothing changes: Explain selects only targets whose symbol is not already held; every resize target is held, and the idle row has no evidence, so resize rows are never explained | 6: existing `commands/explain.py` selection |
| `book_previews` on a resize night (§5 Q2) | Keep today's code: on any decision night the preview is the decision itself (the frozen basket at the new exposure); on a non-decision night it is the fresh `force=True` rank. The page shows "would pick now" only when there is no pending decision, so a resize night shows the orders instead | 6: surrounding convention (`_step_book` preview rule) |
| `RESIZE_BAND` (1% ≈ $5.58 on $558) as the trim/top-up floor (§5 Q3) | Unchanged — it is a rule-set lever and the rules are a closed record; the site mirrors it ("No change" under 1% of equity) | 1: invariant 3 |
| Replay of a resize decision: where its `last_rank` and marks come from | `expected_book` tracks its own expected rank decision (pre-idle) and uses `last_close(market, symbol, data_date)` for held symbols as marks — independent of the stored rows, so the check stays a check | 6: surrounding convention (replay recomputes, never reads the stored decision) |
| "A split inside the month" acceptance | `paper_check` must not report `mismatch`; `split-affected` is the judge's defined status when the split hits a held/pending symbol; separately a pure test asserts the post-split resize decision equals `run_book`'s | 6: existing `judge` contract |
| Trim/top-up cell: all book strategies or split-cadence only | Split-cadence only; every other strategy's page renders as before | 5: user raw input §4.6 ("For a split-cadence strategy …") |
| How the web knows a strategy is split-cadence | A fixed set of rules ids read from `Strategy.rulesId` | 6: convention (`rulesId` already on `Strategy`; no new column) |
| Order row for a symbol the split-cadence book does not hold yet | "Buy about $X" for the whole target, with no band applied; Add / Trim / No change only for held symbols | 6: surrounding code (`sim/book.py` applies `RESIZE_BAND` only to `add`/`trim` of a held position) |
| How the promote end-to-end test names a split-cadence allocator | Lab variant `M0022-W-TV14` with its `RESOLVER`/`EVIDENCE` entries added by `monkeypatch` inside the test only; nothing committed | 4: plan index (On Landing: this set must not promote M0022 or touch the roster) |
| Phase 2's end-to-end tests: reuse phase 1's in-memory helpers or build a Postgres world | Its own scripted Postgres world in `test_paper_split_cadence.py`; no edits to phase 1's test files | 3: the plans' code blocks (phase 2's world needs DB rows and a resolver-named object, which `BREATHE` is not) |

## Open Questions

(none)

## On Landing

The session "analyze-why-this-pick-pipeline" asked, on the owner's behalf, to hear when this set has
landed on `main` and been verified. Whoever lands the set (the coordinator, or the last phase's
session) sends it ONE line with SendMessage (`to: "analyze-why-this-pick-pipeline"`) giving: the
merge commit on main; the preset id `monthly-rank-weekly-resize-frac`; and anything a promote of a
split-cadence candidate needs beyond `promote --fractional` (as of this plan: its allocator's
RESOLVER and EVIDENCE entries, like any promotion — nothing split-specific).

That session owns the roster change. This set must NOT promote M0022, touch the RM-FR roster
entry, or change `PAPER_PAUSED` in `nightly.yml`.

## Rollback

Per phase: revert the phase's commit. Phase 2 without phase 1 is impossible (depends). Reverting
phase 1 alone restores the refusal; phase 2's tests would then fail, so revert 2 first. Phase 3 is
independent. Whole set: revert the merge; no migration or data to undo, and no roster row uses
the new code path until a split-cadence method is promoted.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f PAPER_SPLIT_CADENCE_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows:

    /analyze-orchestrator -f PAPER_SPLIT_CADENCE_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan PAPER_SPLIT_CADENCE_PLAN.md

# Plan: "Why this pick" pipeline — per-pick evidence, explained by the LLM

**Slug:** why-this-pick-pipeline
**Date:** 2026-10-06 21:34
**Analysis:** `20261006-213425-W7P3_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/why-this-pick-pipeline`
**Branch:** `feature/why-this-pick-pipeline` (base: `origin/main` @ `3dd43e3`)
**Phases:** 5
**Status:** phases 1, 2 of 5 complete
**Coordinator:** —

---

## Why

The user, verbatim:

> also, you know, in the UI, we provide user with this field "Why this pick" . but truth be told, 99% of our methods is just mathematical formula right? can we think of a pipeline where any method that recommend some stocks can pass its predictions to LLM , and LLM can provide the natural concise non-technical text for "Why this pick" . you know, for each stock recommended by a method, they must have their own reason , different than each other .

Approved as proposed: each method exposes the numbers its formula used on each stock; the LLM
turns them into one or two plain sentences; facts only (every number in the text must be in the
facts, checked automatically), no predictions, no buy advice; C keeps its news reason as a second
line; evidence is a requirement before a lab method can be promoted to the site. The owner is not
a trader: plain words, no ids or codes on the site.

Today's production texts (2026-10-06) show the bugs: order-mechanics boilerplate ("This is a paper
trade … a buy limit order for 10 PFE shares at $27.15 …"), two NULLs, two cut mid-sentence.
Root cause (analysis): `explain` calls `glm-5.3` with thinking on and `max_tokens` 400, so
reasoning eats the budget; `clean()` also cuts at 600 chars with "…".

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Every method that recommends stocks exposes per-pick evidence: the numbers its formula used | 1, 2 |
| R2 | Explain passes those facts to the LLM → 1–2 plain sentences per pick, distinct per stock | 3 |
| R3 | Facts only, no predictions, no buy advice; every number checked against the facts; failing text discarded; never fails the night | 3 |
| R4 | Fix today's bugs: boilerplate, NULL, truncated texts | 3 |
| R5 | C keeps its news-check reason as a second line | 5 |
| R6 | "Would pick now" rows get reasons too, if cheap | 2, 5 |
| R7 | Evidence is required before a lab method is promoted to the site | 4 |
| R8 | Plain words for a non-trader; no ids/codes on the site | 1, 3, 5 |

## Scope

**In scope:** a pure evidence module; storing evidence with every paper entry (orders,
book_targets, book_previews); rewriting Explain's prompt, LLM settings and acceptance checks;
a promote gate; showing explanation / facts on Positions and Today; docs.
**Out of scope:** changing any strategy's decisions, params, rules or digest; re-explaining
entries written before this ships; the Veto step and its frozen prompt (`c-veto-v1`); backtests;
lab methods' own files (frozen once run).

## Invariants

1. End of every phase, in the worktree (its own `engine/.venv` and `web/node_modules` exist; never
   use main's): `docker start seer-pg`, then
   `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
   passes except the two known pre-existing Python-3.12-only failures
   (`test_f_fundamental.py::test_allocator_shape`,
   `test_market_fundamentals.py::test_adding_the_hook_does_not_change_the_allocator_check`);
   `engine/.venv/bin/ruff check engine` is clean; `cd web && npx vitest run && npx tsc --noEmit` passes.
2. **Frozen roster.** No params class, `as_dict`, object, rules or `RESOLVER` entry changes;
   `tests/test_paper_roster.py::PINS` digests never move. Evidence lives in a new module.
3. **Decisions unchanged.** Paper's orders, targets, fills, trades and snapshots are byte-for-byte
   what they were; `paper_check` stays green. `evidence` never enters `replay.Records` or `compare`.
4. **Pure means pure.** `strategies/evidence.py` is under `strategies/`, so
   `tests/test_strategy_purity.py` scans it: no psycopg/requests/time/random/logging/IO, no clocks.
5. **Never fails the night.** An evidence function that raises → that strategy's evidence is
   NULL for the night (logged in `paper.py`), the decision is still stored. Explain always exits 0.
6. **Design §1.** No text presents a pick as a buy; Explain's SYSTEM prompt keeps "never recommend
   buying or selling, never predict prices". Today's "SPY buy-and-hold is the champion" stays.
7. **UI law.** Seer v2 design; every button icon-only (Lucide) with `aria-label` and `data-tip`;
   414 pt and desktop; light and dark. Nothing on the site shows ids, digests, column names or
   indicator codes (`RSI(2)`, `SMA200`, `12-1`).
8. **File ownership.** `strategies/evidence.py`, `tests/test_evidence.py`: phase 1.
   `db/migrations/009_evidence.sql`, `paper/store.py`, `commands/paper.py`,
   `tests/test_paper_evidence.py`: phase 2. `commands/explain.py`, `tests/test_explain.py`,
   `tests/test_paper_c.py` (one assertion, line 490), `engine/src/seer_engine/llm.py` (docstrings
   only), `docs/runbooks/paper-trading.md`, `engine/package_readme.md`: phase 3 — the two doc files
   also carry phase 2's Paper/evidence lines and phase 4's promote condition, so no other phase edits
   them. `commands/promote.py`, `tests/test_promote_command.py`,
   `.claude/skills/explore-and-experiment-new-method/SKILL.md`: phase 4. `web/**` (including
   `web/package_readme.md`, `web/scripts/seed-demo.mjs`): phase 5. Phases 3, 4 and 5 share no file
   and may run at the same time. (Phase 2's tests *import* `test_paper_c`'s helpers; they never edit it.)

## Contracts every phase codes against

### K1 — `engine/src/seer_engine/strategies/evidence.py` (phase 1, pure)

```python
Facts = tuple[str, ...]
"""One pick's evidence: 2–6 short plain-English statements, each with its numbers already
formatted for a reader ("$231.40", "6.1%", "3rd of 412"). No ids, no indicator codes."""

EvidenceFn = Callable[[Market, Any, date, Sequence[str]], dict[str, Facts]]
"""(market, params, data_date, symbols) -> {symbol: facts} for every symbol it can explain
(a symbol it cannot explain is absent). Reads only bars dated <= data_date and panel facts
filed <= data_date. Pure; may raise on bad input (the caller catches)."""

EVIDENCE: dict[str, EvidenceFn]
"""Keyed by paper.roster.RESOLVER keys: "STRATEGY_A", "STRATEGY_C", "FACTOR", "TIMING",
"FUNDAMENTAL". The benchmark key has no entry. A test pins
set(EVIDENCE) == set(roster.RESOLVER) - {roster.BENCHMARK_OBJECT}."""

def evidence_for(object_name: str, market: Market, params: Any, data_date: date,
                 symbols: Sequence[str]) -> dict[str, Facts]:
    """EVIDENCE[object_name](...); KeyError for an unknown name."""

def has_evidence(object_name: str) -> bool: ...
```

`evidence_for` and `has_evidence` read `EVIDENCE` **at call time** (phase 2 and phase 4 tests patch
the dict). No fact contains a word Explain's `BANNED` list rejects (buy, sell, recommend, should,
will, going to, expect, guarantee); phase 1's tests enforce it.

Fact content (plain words, numbers formatted; the phase-1 planner fixes exact wording):
- **STRATEGY_A**: last close and how far above its 200-day average; the 2-day strength score
  (Wilder RSI(2), described as "a 2-day strength score of 4 out of 100; below 10 counts as a sharp
  short drop" — never the code "RSI(2)"); the % change over the last 2 and 5 sessions; average
  daily trading value; its place among tonight's qualifying stocks ("1st of 10 that qualified").
- **STRATEGY_C**: STRATEGY_A's facts computed with `params.a`.
- **FACTOR** (F4): the momentum return in plain words ("rose 48.2% over the 12 months up to a
  month ago" — months from `mom_n`/`mom_skip`); its place among eligible stocks ("3rd of 412");
  the market filter when `params.trend` is set ("SPY closed 4.1% above its 200-day average, so the
  method is allowed to hold stocks" — "hold", never "buy"); volatility only when the ranking reads it
  (`lowvol`, `mom_lowvol`). Exact templates: phase-1.md "Fact strings".
- **TIMING** (F1): the signal instrument's close vs its average over `n` days, and what that
  means ("SPY closed at $671.20, 8.3% above its 200-day average of $619.80, so the rule says hold").
- **FUNDAMENTAL** (FND): place among eligible ("5th of 380"); each factor the ranking reads, in
  words with its value and how it compares to the eligible set ("earns 31% on its shareholders'
  money — higher than 92% of the companies checked"); how old the latest filing is.

### K2 — storage (phase 2)

```sql
-- db/migrations/009_evidence.sql
ALTER TABLE orders        ADD COLUMN IF NOT EXISTS evidence jsonb;  -- JSON array of strings, NULL = none
ALTER TABLE book_targets  ADD COLUMN IF NOT EXISTS evidence jsonb;
ALTER TABLE book_previews ADD COLUMN IF NOT EXISTS evidence jsonb;
```

`paper/store.py`: `insert_pending_orders(..., evidence: Mapping[str, Sequence[str]] | None = None)`,
`save_book_decision(..., evidence=None)`, `save_book_preview(..., evidence=None)` — keyword-only,
default None, existing callers unchanged; a symbol absent from the mapping stores NULL.
`commands/paper.py` computes evidence through one helper that catches every exception
(Invariant 5), with `market = tonight.view(s)` (the decision's own view) and the decided symbols.
The idle instrument (`rules.idle_symbol`) gets no evidence.

### K3 — Explain (phase 3)

Reads `evidence` with each entry; an entry with NULL/empty evidence is skipped (stays NULL).
Prompt = the facts + the strategy's plain name + the task "in at most 2 short plain sentences,
say why this method picked this stock, using only these facts". LLM call:
`client.complete(SYSTEM, prompt, temperature=0.0, thinking="disabled", max_tokens=EXPLAIN_MAX_TOKENS)`.
`accept(text, facts, earlier) -> str | None`: complete sentence(s) only, ≤ 2 sentences,
≤ `MAX_CHARS`, every number in the text present among the facts' numbers, no banned phrase
(buy/sell advice, predictions), not identical to an earlier text in the same batch; else None
(discarded, logged, stays NULL). Never appends "…".

### K4 — promote gate (phase 4)

`promote` refuses (exit 2, `NotPromotable`) when the candidate's allocator's object name has no
evidence function (`not evidence.has_evidence(name)`), saying in one line what to add.

### K5 — web (phase 5)

Reads `evidence` via `to_jsonb(<row>) -> 'evidence'` so the query works before 009 is applied
(Vercel deploys on push; the nightly Migrate applies 009 later). "Why this pick" shows the LLM
text; when it is NULL and evidence exists, the facts themselves (a short list); "unavailable"
only when both are missing. "Would pick now" rows get a "Why it's on the list" toggle showing
their facts. C's "Why it passed the news check" line stays.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 ✅ | Pure evidence module | R1, R8 | `engine/strategies` | 2 | — | HARD | `.workflows/plan/why-this-pick-pipeline/phase-1.md` | P1-ENG-A1SZ | — |
| 2 ✅ | Store evidence with every paper entry | R1, R6 | `engine/paper`, `db` | 4 | 1 | NORMAL | `.workflows/plan/why-this-pick-pipeline/phase-2.md` | P1-ENG-H5LC | — |
| 3 | Explain from evidence, with checks | R2, R3, R4, R8 | `engine/commands`, docs | 6 | 2 | HARD | `.workflows/plan/why-this-pick-pipeline/phase-3.md` | P1-ENG-Q0OH | — |
| 4 | Promote requires evidence | R7 | `engine/commands`, skill | 3 | 1 | EASY | `.workflows/plan/why-this-pick-pipeline/phase-4.md` | P1-ENG-BZYN | — |
| 5 | Show reasons on the site | R5, R6, R8 | `web` | 9 | 2 | NORMAL | `.workflows/plan/why-this-pick-pipeline/phase-5.md` | P1-WEB-YJSP | — |

### Phase 1 — Pure evidence module
**Satisfies:** R1, R8
**Owns:** `engine/src/seer_engine/strategies/evidence.py` (K1), `engine/tests/test_evidence.py`.
**Does not touch:** any existing strategy module, params, roster, paper, explain, web.
**Exit criteria:** every RESOLVER object (except the benchmark) has an evidence function; tests
show distinct facts per symbol on synthetic markets, plain wording (no "RSI", "SMA", ids, and no
advice/prediction word from Explain's `BANNED` list), no look-ahead (facts identical when bars after
data_date are added), purity test green; `EVIDENCE` read at call time.

### Phase 2 — Store evidence with every paper entry
**Satisfies:** R1, R6
**Owns:** migration 009 (K2), `paper/store.py` evidence parameters, `commands/paper.py` evidence
helper and calls (bracket orders in `_start`/`_step_bracket`, book targets and previews in
`_start`/`_step_book`), `engine/tests/test_paper_evidence.py`.
**Does not touch:** decisions, replay, explain, web, docs.
**Exit criteria:** after a paper night every pending A and C order and every non-idle target /
preview row has evidence (idle symbol NULL; a TIMING-off night explains nothing); an evidence
function that raises leaves NULL and the night succeeds; `paper_check` green; existing paper tests
unchanged and green.

### Phase 3 — Explain from evidence, with checks
**Satisfies:** R2, R3, R4, R8
**Owns:** `commands/explain.py` (K3), `tests/test_explain.py`, `tests/test_paper_c.py:490` (one
assertion), `llm.py` docstrings, `docs/runbooks/paper-trading.md` (Explain section, the night tree's
Paper evidence line and Explain line), `engine/package_readme.md` (pipeline overview, migration 009,
and the `promote` section's third condition).
**Does not touch:** paper, store, veto, promote code, web.
**Exit criteria:** prompt built from evidence only; LLM call disables thinking with temperature 0;
accept() rejects invented numbers, cut-off text, >2 sentences, banned phrases, duplicates; no "…";
entries without evidence skipped; always exit 0; phase 1's exact fact shapes pass `vet`.

### Phase 4 — Promote requires evidence
**Satisfies:** R7
**Owns:** `commands/promote.py` gate (K4), `tests/test_promote_command.py`, the explore skill's
promotion steps (one rule: a promotable allocator needs an `EVIDENCE` entry and a `RESOLVER` entry).
**Does not touch:** evidence module contents, roster, lab methods, `engine/package_readme.md`
(phase 3 documents this gate there).
**Exit criteria:** promote of a candidate whose object has no evidence exits 2 with a one-line
reason; existing promote tests green.

### Phase 5 — Show reasons on the site
**Satisfies:** R5, R6, R8
**Owns:** `web/lib/why.ts` + `why.test.ts` (new), `web/lib/data.ts` (evidence on PendingOrder,
Pick, PreviewPick via `to_jsonb`), Positions `OrderRow` and `WouldPick`, Today `PickCard`,
`WhyToggle.tsx` + its CSS (facts list), `web/scripts/seed-demo.mjs` (demo evidence in phase 1's
exact wording, demo previews), `web/package_readme.md`.
**Does not touch:** engine.
**Exit criteria:** K5 behaviour; vitest covers the explanation/facts fallback helper; tsc clean;
screens checked at 414 pt light and dark.

## Reconciliation Log

| # | Conflict | Class | Phases | Resolution |
|---|---|---|---|---|
| 1 | Phase 1's market-filter fact (FACTOR, and FUNDAMENTAL when `trend` is set) said "so the method is allowed to **buy** stocks"; phase 3's `BANNED` rejects `\bbuy\b` with no facts exception, so every faithful note restating it would be discarded, and phase 5 shows facts verbatim when there is no note. Found by running phase 3's `vet` over every phase-1 prototype fact (12 rejections, all this sentence). | Contract drift / collision | 1, 3, 5 | Phase 1 wording is now "allowed to **hold** stocks" (template, code, test, real output). Phase 1's `FORBIDDEN` also rejects every `BANNED` word. Re-run: 0 rejections, prototype test file 34/34 green. Phase 3 gains `test_phase_one_fact_shapes_pass_the_checks`, which pins phase 1's exact shapes against `vet`/`numbers_in` (ordinals, `$124 million`, `200-day`, `12 months ago to 1 month ago`, percentages, `$1,231.40`). |
| 2 | Phase 3 edits `tests/test_paper_c.py:490` and `llm.py` docstrings, which are on no phase's ownership list. | Ownership gap | 3 | Granted to phase 3 in invariant 8. No other phase edits them (phase 2 only imports `test_paper_c` helpers). |
| 3 | Phases 2 (`monkeypatch.setitem(EVIDENCE, "FACTOR")`) and 4 (`monkeypatch.delitem(EVIDENCE, "FUNDAMENTAL")`) assume `EVIDENCE` is read at call time; phase 1 did not state it. | Unmet assumption (unpinned) | 1, 2, 4 | Verified: phase 1's code does `EVIDENCE[object_name]` / `object_name in EVIDENCE`. Now stated in phase 1's contract and K1. Phase 4's conditional fallback note removed. |
| 4 | Phase 2's whole-night test asserted facts on *every* F4/F1 target/preview and `F1 targets == ["SPY"]*n`, which an idle row or a TIMING-off night (TIMING returns `{}`) would break. | Brittle assertion vs contract | 1, 2 | Test now skips the idle symbol (and asserts idle rows are NULL), requires facts on every non-idle row, and checks F1's non-idle symbols are `{"SPY"}`. |
| 5 | That C orders get evidence was proven only in phase 3 (`test_paper_c` via `explain`), so a phase-2 or phase-1 break would surface one phase late. | Gap | 2 | Phase 2 adds `test_c_orders_carry_a_facts_under_c_params` (C world via `test_paper_c.night(..., allow_all)`); exit criteria include C. |
| 6 | Phase 4 changes `promote`'s refusals but `engine/package_readme.md`'s `promote` section ("Promotable means two things") belongs to phase 3, and no phase updated it. | Gap | 3, 4 | Phase 3 step 6h adds the third condition. Phase 4 keeps off the file, so 3/4/5 stay file-disjoint. |
| 7 | Phase 2's handoff asked phase 3 to document the evidence column and the Paper warning line in the runbook; phase 3 covered only Explain. | Gap | 2, 3 | Phase 3 step 5a' adds the night tree's Paper evidence line with the warning text; 5e names the warning line. |
| 8 | Later phases quoted fact wording that phase 1 does not produce: phase 3's runbook example ("That ranked 3rd of 412 eligible stocks") and phase 5's demo facts (own phrasing, a "market filter is on" line, and the existing demo text "ranks first by 12-1 momentum", a code invariant 7 forbids). | Stale quote | 1, 3, 5 | Runbook example and every demo fact rewritten in phase 1's exact templates (incl. "hold stocks"); demo `$` formats like `_money`; the `12-1` demo text says it in words. |
| 9 | Invariant 1's verification was incomplete: phase 1 and 3 lacked the web `vitest`/`tsc` step, phase 4 ran only two test files, phase 5 mentioned the engine run without commands. | Verification gap | 1, 3, 4, 5 | Each phase's Verification now has the full invariant-1 commands, including the two known Python-3.12-only failures. |

Checked, no conflict: phase 2 writes `Jsonb(list)` (a real array, never `[]`), phase 5 reads `to_jsonb(alias)->'evidence'` and treats a non-array as null; phase 3's `facts_from` likewise. Dependencies 1 → 2 → 3, 1 → 4, 2 → 5 all point backward; phase 5 needs 009 only for the demo seed (its queries tolerate a missing column), phase 3 needs 009 for its seeds and phase 2's paper writes for `test_paper_c`. No phase deletes anything another phase uses (phase 3's deletions are private to `explain.py`; its `FakeClient` keeps the constructor and reply `test_paper_c` imports).

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Evidence on the strategy objects vs a separate module | separate pure module keyed by RESOLVER name | 1: invariant 2 (frozen roster, closed records) |
| Where evidence is computed | Paper, at decision time, stored as jsonb | 1: invariant 3/5 — same data as the decision; Explain stays DB-only |
| LLM text for "would pick now" previews | no LLM: show the stored facts (deterministic, free) | 4: R6 "if cheap" — previews are replaced every night |
| NULL explanation with evidence present | show the facts instead of "unavailable" | 5: user's raw input ("each stock must have its own reason") |
| Re-explain entries written before this ships | no | Scope: out of scope; new entries are written every night |
| Market-filter fact: keep "allowed to buy stocks" (and let Explain allow `buy` when the facts use it) vs reword | reword to "allowed to hold stocks"; `BANNED` unchanged | 1: invariant 6 (no text presents a pick as a buy; facts are shown verbatim on the site) |
| Who documents phase 2's Paper evidence and phase 4's promote gate | phase 3, the owner of both doc files | 1: invariant 8 (one owner per file) — keeps 3, 4, 5 concurrent |
| Demo facts in the seed: free phrasing vs the engine's exact templates | phase 1's exact templates | 1: invariant 7 (no codes on the site) + rule "later phases quote post-change state" |
| Whole-night evidence test on idle / TIMING-off rows | idle rows must be NULL, every non-idle row must have facts | 2: phase 2's exit criteria ("idle symbol NULL") and K1 (TIMING returns `{}` when the rule is off) |

## Open Questions

(none)

## Rollback

Per phase: revert its commit. 009 is additive (nullable columns); reverting code leaves the
columns unread. Whole set: revert the merge; Explain falls back to the old prompt.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f WHY_THIS_PICK_PIPELINE_PLAN.md --phase 1

Or run the whole set as a swarm:

    /analyze-orchestrator -f WHY_THIS_PICK_PIPELINE_PLAN.md

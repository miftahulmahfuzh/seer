# Code Analysis: "Why this pick" pipeline (per-pick evidence → LLM explanation)

**Type:** Feature Implementation
**Date:** 2026-10-06 21:34
**Session ID:** 20261006-213425-W7P3
**Plan:** `WHY_THIS_PICK_PIPELINE_PLAN.md` (5 phases)
**Worktree:** `/home/miftah/.worktrees/seer/why-this-pick-pipeline`, branch `feature/why-this-pick-pipeline` (base `origin/main` @ `3dd43e3`)

---

## User Input

### Original User Request

The user's message in the conversation (verbatim):

> also, you know, in the UI, we provide user with this field "Why this pick" . but truth be told, 99% of our methods is just mathematical formula right? can we think of a pipeline where any method that recommend some stocks can pass its predictions to LLM , and LLM can provide the natural concise non-technical text for "Why this pick" . you know, for each stock recommended by a method, they must have their own reason , different than each other .
>
> what do you think?

The assistant's proposal, which the user then approved with "yes, /analyze and build the why-this-pick pipeline":

> To get a different, real reason for each stock, the LLM has to see the numbers the formula actually used on that stock … F4 (momentum): "up 48% over 12 months, 3rd strongest of ~500, trading above its 200-day average." A: "dropped 7% in 5 days, more than usual for it." FND: the specific company numbers that ranked it high. The LLM turns those into one or two plain sentences. … Facts only. The LLM can only restate the numbers it's given: no outside news, no predictions. We can check this automatically (every number in its text must be in the facts). What the formula saw, not why the stock will rise. … The work is giving each method a small "here are my reasons for this pick" output. That's one per method, and I'd make it a requirement for any lab method before it can go on the site. … C keeps its news reason as a second line.

/analyze arguments as given:

> Build the "Why this pick" pipeline for Seer: every method that recommends stocks (A, C, F4-MOM12-N20-TREND, F1-SPY-SMA200-M, FND, and any lab-promoted method) exposes per-pick evidence — the actual numbers its formula used for that stock (e.g. F4: 12-month return, rank of N, above 200-day average; A: 5-day drop vs its usual; FND: the fundamental factors that ranked it). The nightly Explain step passes those facts to the LLM, which writes 1–2 plain, non-technical sentences per pick, distinct per stock. Rules: facts-only (no outside news, no predictions; every number in the text must appear in the facts, checked automatically; a failing text is discarded -> "unavailable"), never a buy recommendation (design §1), never fails the night. Fix today's bugs: explanations are boilerplate order mechanics, some NULL, some truncated mid-sentence. C keeps its news-check reason as a second line. Book previews ("would pick now") may also get reasons if cheap. Evidence becomes a requirement for lab methods before promotion to the site. Owner is not a trader: plain words, no ids/codes on the site.

### User-Provided Context

Production, session 2026-10-06 (`orders.explanation`):
- `A INCY`: "This is a paper trade simulated by the Seer research app under Strategy A (… 5-day brackets), not a recommendation to buy, and it places a limit order to buy 2 INCY shares at $112.47 … Under the design-v0 rules," (cut mid-sentence)
- `A JNJ`: "This is a paper trade simulated by the Seer" (cut)
- `C PFE`, `C TGT`: NULL

### User-Provided Files
None.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Every method that recommends stocks (A, C, F4, F1, FND, any promoted lab method) exposes per-pick evidence: the actual numbers its formula used for that stock |
| R2 | The nightly Explain step passes those facts to the LLM, which writes 1–2 plain, non-technical sentences per pick, distinct per stock |
| R3 | Facts-only rules: no outside news, no predictions, never a buy recommendation; every number in the text must appear in the facts (checked automatically); a failing text is discarded → "unavailable"; never fails the night |
| R4 | Fix today's bugs: boilerplate order-mechanics text, NULL explanations, text truncated mid-sentence |
| R5 | C keeps its news-check reason as a second line |
| R6 | Book previews ("would pick now") get reasons too, if cheap |
| R7 | Evidence becomes a requirement for a lab method before it can be promoted to the site |
| R8 | Plain words for a non-trader owner; no ids, codes or jargon on the site |

---

## Detailed Requirements Understanding

**Problem.** "Why this pick" (`orders.explanation`, `book_targets.explanation`) is written by
`commands/explain.py`. Its prompt (`prompt_for`, explain.py:200) carries only order mechanics:
symbol, last close, limit, take-profit, stop, shares, weight, and the `describe_rules` text. The
LLM therefore cannot say *why the formula chose the stock*, because the numbers the formula ranked
on (RSI, SMA distance, 12-1 momentum, rank among eligible, fundamentals) are never stored or passed.
The same prompt also asks it to "say that it is a paper trade", so every text opens with identical
boilerplate.

**Truncation and NULL root cause.** `explain.run` builds `llm.Client(cfg)` with
`DEFAULT_MAX_TOKENS = 400` (llm.py:42) and calls `client.complete(SYSTEM, prompt)` with no
`thinking`/`temperature`/`max_tokens` overrides (explain.py:283). The configured model `glm-5.3`
thinks by default, so reasoning tokens consume the 400-token budget: the visible text stops
mid-sentence ("…under Strategy A … Under the") or is empty, and an empty reply raises
`LlmError("empty explanation")` → NULL. Strategy C's veto avoids exactly this by passing
`thinking="disabled"`, `temperature=0`, `max_tokens=1024` (strategies/c.py `CParams`).
`clean()` (explain.py:236) also cuts at `MAX_CHARS = 600` and appends "…", a second source of
mid-sentence endings.

**Success criteria.**
1. Each paper entry (bracket order, book target, book preview) stores the evidence its method
   computed for that symbol on the decision night: a short list of plain-language facts with
   numbers.
2. Explain sends those facts (no order mechanics boilerplate) and writes ≤ 2 complete sentences
   per pick; texts differ between picks because the facts differ.
3. A text whose numbers are not all present in its facts, or that is not a complete sentence, or
   that is empty, is discarded (NULL → the site says "unavailable"); the night never fails.
4. LLM call uses thinking disabled, temperature 0, enough max_tokens; no mid-sentence text.
5. C's order shows the explanation and, separately, the news check's reason (already shipped in
   `3dd43e3`; must survive).
6. "Would pick now" rows show a reason.
7. `promote` refuses a lab method whose allocator has no evidence function.
8. Nothing on the site shows ids, digests, column names or indicator codes ("RSI(2)", "SMA200").

**Key considerations / constraints.**
- Design §1: never present a pick as a real-money buy. The SYSTEM prompt keeps "never recommend".
- Purity: `strategies/*.py` and `paper/*.py` (except store.py) are purity-tested
  (`tests/test_strategy_purity.py`). Evidence functions must be pure too.
- Frozen roster: digests of SPY, A, F4, F1, C, FND must not move. Digests come from
  `roster.strategy_params(e)` = params `as_dict` + object name + rules (not code). Adding new
  functions next to an object does not change a digest; changing `AParams`/`FactorParams`/
  `as_dict` would. Evidence must not touch any params class.
- Closed records: `strategies/a.py` (`STRATEGY_A`, `STRATEGY_A_PARAMS`) and the backtest runners
  are "closed records" in earlier plans; evidence lives in a NEW module and only imports public or
  module-level helpers (`a.features_at`, `f_factor.factor_rows`/`rank_rows`/`trend_on`,
  `f_index.timing_state`/`above_sma`, `f_fundamental.fundamental_rows`/`rank_rows`/
  `composite_scores`/`trend_on`).
- Replay (`paper_check`) compares orders/targets/fills/trades field by field (`replay.compare`).
  A new `evidence` column must NOT enter `Records` or `compare`, so the check stays green.
- Paper's night is one transaction; evidence computation must never raise out of it. A method
  whose evidence function fails stores `evidence = NULL` (explain then has nothing and leaves the
  text NULL), never fails the night.
- `book_previews` (migration 008, shipped `3dd43e3`) is replaced every night; an explanation on
  it would need re-explaining every night (cost ~3 strategies × ≤ 20 rows). Cheaper: show the
  stored facts directly (deterministic, no LLM). See plan Decisions.
- The LLM is shared with Veto (`LLM_MODEL` = `glm-5.3`); Explain is not frozen into any spec, so
  changing its prompt/settings needs no new roster id.

**Assumptions.**
- The nightly order is Nightly → Veto → Paper → Paper check → Explain (`.github/workflows/nightly.yml`).
  Explain reads evidence the same night Paper wrote it.
- Number check granularity: a number in the text "appears in the facts" when its normalized form
  (strip `$`, `,`, `%`, `+`, trailing `.0`) equals a normalized number token found anywhere in the
  fact strings (labels or values). Spelled-out small numbers ("two days") are not checked.

---

## Analysis Scope

### Discovered Related Files

- `engine/src/seer_engine/commands/explain.py` — the Explain step (all of it)
- `engine/src/seer_engine/llm.py` — `Client.complete` (thinking/temperature/max_tokens overrides), `DEFAULT_MAX_TOKENS = 400`
- `engine/src/seer_engine/commands/paper.py` — `_start`, `_step_bracket`, `_step_book` (where decisions are made and stored)
- `engine/src/seer_engine/paper/store.py` — `insert_pending_orders`, `save_book_decision`, `save_book_preview`
- `engine/src/seer_engine/paper/bracket.py` — `decide_bracket` returns `sized.placed` (Orders)
- `engine/src/seer_engine/paper/roster.py` — `RESOLVER` (object_name → Binding), `RosterEntry` (`obj`, `params`, `engine`, `rules`)
- `engine/src/seer_engine/strategies/a.py` — `Features`, `features_at(history, data_date)` (close, sma, rsi, atr, dollar volume), `AParams`
- `engine/src/seer_engine/strategies/c.py` — `NewsVeto` (picks = A's candidates filtered by stored verdicts), `CParams.a`
- `engine/src/seer_engine/strategies/f_factor.py` — `FactorRow`, `factor_rows`, `rank_rows`, `trend_on`, `FactorParams` (F4 = rank momentum, top 20, 12-1 momentum, trend SPY/200)
- `engine/src/seer_engine/strategies/f_index.py` — `TimingParams`, `timing_state`, `above_sma` (F1 = hold SPY when SPY close > SMA(200))
- `engine/src/seer_engine/strategies/f_fundamental.py` — `FundamentalRow`, `fundamental_rows`, `composite_scores`, `rank_rows`, `trend_on`, `FUNDAMENTAL_PARAMS`, `MarketAware` path (`prepare_market`)
- `engine/src/seer_engine/strategies/allocator.py` — `Allocator`, `MarketAware`, `prepare_for`
- `engine/src/seer_engine/strategies/indicators.py` — window functions (`return_window`, `sma_window`, …)
- `engine/src/seer_engine/backtest/market.py` — `Market` (history, membership, fundamentals)
- `engine/src/seer_engine/commands/promote.py` — `object_name_of`, `NotPromotable`, `build_promotion`
- `engine/src/seer_engine/lab/method.py` — `Method`, `Candidate` (allocator per variant)
- `engine/tests/test_strategy_purity.py` — purity scan of strategies/ and paper/
- `engine/tests/test_explain.py`, `test_paper_command.py`, `test_paper_check.py`, `test_promote_command.py`
- `db/migrations/003_paper.sql` (orders, book_targets with `explanation text`), `008_book_kickoff.sql` (book_previews)
- `web/lib/data.ts` — `pendingOrders` (explanation), `bookPreview`, picks for Today
- `web/app/(app)/positions/page.tsx` — `OrderRow` (WhyToggle explanation + C's "Why it passed the news check"), `WouldPick`
- `web/app/(app)/page.tsx` — Today `PickCard` WhyToggle
- `web/components/WhyToggle.tsx`
- `web/scripts/seed-demo.mjs` — demo explanations
- `.claude/skills/explore-and-experiment-new-method/SKILL.md` — promotion steps
- `docs/runbooks/paper-trading.md`, `engine/package_readme.md`

---

## Current Dataflow

### Entry point: nightly workflow

`.github/workflows/nightly.yml`: Migrate → Nightly (bars) → Veto (C's news check) → Paper → Paper check → Explain.

### Decision (Paper)

1. `commands/paper.py:_trade` loads the market window once (`store.load_market_window`), then for
   each roster entry: `_start` (first night) or `_step_bracket` / `_step_book` / `_step_benchmark`.
2. Bracket (A, C): `decide_bracket(portfolio, strategy, params, view.history, members, s)` →
   `sized.placed` (Orders) → `store.insert_pending_orders(conn, id, sized.placed)` → rows in
   `orders` (status 'pending', `explanation` NULL). For C the strategy is `NewsVeto(allowed=…)`
   built by `_bracket_strategy`. The picks come from `STRATEGY_A.picks(...)` = ranked `Pick`s.
3. Book (F4, F1, FND): `decide_book(view, e.obj, e.params, rules, s, held, force=kickoff)` →
   `Target`s → `store.save_book_decision` → `book_targets` (explanation NULL). On the last
   session `save_book_preview` replaces `book_previews` (no explanation column).
4. Nothing about *why* a symbol qualified is stored anywhere: features are computed inside
   `features_at`/`factor_rows`/`fundamental_rows` and discarded.

### Explanation (Explain)

1. `explain.run` → `llm.load_config()`; None → log, exit 0.
2. `load_batches`: for each strategy with `pending_session`, bracket orders `status='pending' AND
   explanation IS NULL`, or book targets of the pending session not already held, explanation NULL.
3. `prompt_for(entry)`: order-mechanics facts + rules text + "explain what this paper entry does
   and how the rules would exit it. Say that it is a paper trade".
4. `client.complete(SYSTEM, prompt)` (default max_tokens 400, thinking on by model default).
5. `clean()`: collapse whitespace, cap 600 chars with "…". Empty → `LlmError` → NULL.
6. Per strategy, one transaction `UPDATE … SET explanation = %s WHERE … explanation IS NULL`.
7. 3 failures in a row stop further calls; always exit 0.

### Display (web)

- Positions: `pendingOrders()` → `OrderRow` → `<WhyToggle text={o.explanation} />` ("Why this
  pick"; NULL → "Explanation unavailable for this pick."). For C, an extra line with headline
  count and `<WhyToggle label="Why it passed the news check">` from `news_vetoes.reason`.
- Positions: `WouldPick` lists `book_previews` (rank, symbol, last, weight) — no reason.
- Today: `PickCard` WhyToggle with `p.explanation` (champion picks; SPY is champion, so empty today).

---

## Key Data Structures

- `a.Features` (a.py:115): symbol, close, sma, rsi, atr, dollar_volume (+ index fields).
- `f_factor.FactorRow` (f_factor.py:169): symbol, momentum, volatility, dollar_volume, close, …
- `f_fundamental.FundamentalRow` (f_fundamental.py:307): symbol, close, value, quality, profitability, sue, staleness …
- `f_index.TimingParams`: hold, signal, rule ('sma'), n (200).
- `sim.Pick`, `sim.book.Target` (symbol, weight, last, limit, stop, take).
- `orders`, `book_targets` tables (003): `explanation text`. `book_previews` (008): no explanation.

---

## Dependencies

- Env: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (glm-5.3), shared with Veto.
- Neon via `DATABASE_URL(_UNPOOLED)`; migrations applied by the nightly Migrate step.
- Web uses `@neondatabase/serverless` (HTTP) — a missing column before migrate breaks a query; the
  `bookPreview` loader already guards with try/catch for 008.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `prompt_for` | engine/src/seer_engine/commands/explain.py:200 | def | engine |
| `clean`, `MAX_CHARS` | explain.py:236, :40 | def | engine |
| `load_batches`, `_BRACKET_SQL`, `_BOOK_SQL` | explain.py:136, :57, :64 | def | engine |
| `execute` (explain) | explain.py:259 | def | engine |
| `DEFAULT_MAX_TOKENS` | llm.py:42 | config | engine |
| `insert_pending_orders` | paper/store.py | def | engine |
| `save_book_decision`, `save_book_preview` | paper/store.py | def | engine |
| `_start`, `_step_bracket`, `_step_book` | commands/paper.py | call | engine |
| `RESOLVER` | paper/roster.py:232 | config | engine |
| `features_at` | strategies/a.py:127 | def | engine |
| `factor_rows`, `rank_rows`, `trend_on` | strategies/f_factor.py:194, :256, :234 | def | engine |
| `timing_state`, `above_sma` | strategies/f_index.py:217, :174 | def | engine |
| `fundamental_rows`, `composite_scores`, `rank_rows` | strategies/f_fundamental.py:374, :471, :484 | def | engine |
| `object_name_of`, `NotPromotable` | commands/promote.py:91, :73 | def | engine |
| `OrderRow`, `WouldPick` | web/app/(app)/positions/page.tsx | def | web |
| `PickCard` | web/app/(app)/page.tsx | def | web |
| `pendingOrders`, `bookPreview` | web/lib/data.ts | def | web |
| demo explanations | web/scripts/seed-demo.mjs:87, :177 | config | web |
| explain tests | engine/tests/test_explain.py | test | engine |
| promotion steps | .claude/skills/explore-and-experiment-new-method/SKILL.md:147 | doc | skill |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/evidence.py` (new) — pure evidence functions per RESOLVER object (phase 1)
2. `engine/tests/test_evidence.py` (new), purity test coverage (phase 1)
3. `db/migrations/009_evidence.sql` (new) — `evidence jsonb` on orders, book_targets, book_previews (phase 2)
4. `engine/src/seer_engine/paper/store.py`, `commands/paper.py` — compute + store evidence (phase 2)
5. `engine/src/seer_engine/commands/explain.py` — evidence prompt, LLM settings, checks (phase 3)
6. `engine/src/seer_engine/commands/promote.py` — evidence gate (phase 4); explore skill doc
7. `web/lib/data.ts`, positions page, Today page, seed-demo (phase 5)
8. docs: runbook, engine package_readme (phases 2–4 own their sections)

**This document describes. The plan files prescribe.**

# Code Analysis: Strategy C — A's candidates with a news + LLM veto, on paper

**Type:** Feature Implementation
**Date:** 2026-10-04 17:14 (WIB)
**Session ID:** 20261004-171449-C5V8
**Plan:** `STRATEGY_C_NEWS_VETO_PLAN.md` (7 phases)
**Worktree:** `/home/miftah/.worktrees/seer/strategy-c-news-veto`, branch `feature/strategy-c-news-veto` (base `HEAD` = local `main` @ `d9cecce`; `origin/main` was not resolvable after fetch, and `main` already carries the handover commit)

---

## User Input

### Original User Request

```
/analyze docs/handover/2026-10-04-strategy-c-news-veto.md
```

The handover file is the specification. It is committed on the branch at `docs/handover/2026-10-04-strategy-c-news-veto.md`
(`d9cecce`) and every phase reads all of it. Its §0 in the owner's framing:

> Design §4 names three strategies. A and its rework failed their backtest gates; B (the ML ranker)
> failed its gate too. **C** has never been built. C is A with a second opinion: every night it takes
> the stocks A would buy for the next session, reads the latest news about each one (Finnhub), and
> asks the LLM whether the news says "don't touch this right now" (an earnings miss, fraud, a
> lawsuit, a buyout, a guidance cut...). C buys only what the LLM lets through. If the news or the
> LLM can't be reached, C does **not** buy (design §8: "a failed veto check is no trade").
>
> C can only be tested going forward: an LLM has read the news of the past, so a backtest of C would
> be contaminated (design §4). So C joins the paper roster next to A, and the app shows, month by
> month, whether the veto made A better or worse. Nothing here moves real money.

### User-Provided Context
- Handover §2 "Law: do not reopen" (go-live §1, same code path, frozen roster, closed records, no
  look-ahead, reproducible replay, UI law) and decisions D1–D12; §5 acceptance criteria 1–8; §6 open
  questions (settled below); §7 environment.

### User-Provided Files
- `docs/handover/2026-10-04-strategy-c-news-veto.md`

### Requirement IDs

| ID | What the user asked for (handover §4 "In scope") |
|---|---|
| R1 | Engine, pure: the C strategy object (A's picks filtered by a verdict map, `Strategy` protocol), roster entry `C` with its frozen spec (D5), the prompt text + JSON verdict parser |
| R2 | Engine, impure: `finnhub.py` client, the `veto` command (D6), migration `004` (D7), store read/write for verdicts, `paper` deciding C from stored verdicts, `paper_check` replaying C (D8), `explain` covering C's pending orders |
| R3 | Workflow: `nightly.yml` `Veto` step between `Nightly` and `Paper` (`continue-on-error`, secrets env), within the 45-minute job |
| R4 | Web: C in every roster view; "Vetoed tonight" on Positions; the checklist's D9 row; the demo seed with a C portfolio and verdict rows |
| R5 | Docs: `engine/package_readme.md`, `docs/runbooks/paper-trading.md` (veto step, failure states, owner steps for the new secrets, C's clock), `docs/ROADMAP.md` (P6 with D11 wording) |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** Add a fifth paper portfolio `C` that runs the bracket engine
(`DESIGN_V0`, `sim.size_picks` + `sim.step` via `paper/bracket.py`) on a pick list equal to Strategy
A's ranked picks for the next session, truncated to the first 10, minus every symbol whose stored
news verdict for that session is not `allow`. Verdicts are produced the same night, before `paper`,
by a new impure command `veto` that (a) recomputes A's candidates for `run_dates(now).session_date`,
(b) reads Finnhub company news (and the earnings calendar, see Decisions) published before the
command's start, (c) asks the LLM under a frozen prompt, and (d) stores one row per candidate in a new
`news_vetoes` table. `paper` and `paper_check` read only stored verdicts; the LLM is never re-asked.

**Success Criteria.** Handover §5: (1) the four existing digests are byte-identical and their rows
untouched; (2) C's stored state after ≥ 5 synthetic nights equals the `run_rules(DESIGN_V0)` replay
from stored verdicts, and C == A when every verdict is `allow` (on data where A never reaches past
rank 10); (3) every failure path → no C order for that candidate, never a failed `paper`;
(4) no look-ahead in news or bars; (5) idempotent `veto` and `paper`; (6) UI everywhere incl.
"Vetoed tonight" and the D9 row; (7) CI green with 0 skipped; (8) docs.

**Key Considerations.**
- `strategies.params->'spec'` is computed from **code** and `paper` refuses a started id whose stored
  digest differs (`plan_night` → `store.check_digest`). So everything frozen into C's spec, the model
  name included, must be a code constant (see Decisions).
- `veto` runs before `paper` on C's first night, so verdict rows for `C` exist before C has
  `paper_state`; `paper._has_paper_rows` (the "orphaned rows" guard in `_start`) must not count them.
- A catch-up night (several sessions in one `paper` run) decides earlier sessions too; their verdict
  rows exist only if `veto` ran on that earlier night. Missing verdicts = `failed` = no trade.
- `--require-sessions 5` in `paper_check` counts every roster strategy, so C's younger clock also
  gates the `v0.1.0` operational check (runbook must say so; see Decisions).
- Rate limits: Finnhub 60/min (verified header `X-Ratelimit-Limit: 60`); ≤ 10 candidates × 2 Finnhub
  calls (news + earnings) = ≤ 20 calls/night, spaced ≥ 1.0 s.

**Assumptions.** `glm-5.3` stays the configured model when the owner sets the secrets (it is the
value in `.env.local` today). Finnhub's free calendar keeps answering per symbol.

---

## Analysis Scope

### Explicitly Mentioned Files
`docs/plans/2026-10-03-seer-design.md`, `docs/ROADMAP.md`, `docs/runbooks/paper-trading.md`,
`engine/package_readme.md`, `engine/src/seer_engine/paper/{roster,bracket,replay,store}.py`,
`engine/src/seer_engine/commands/{paper,paper_check,explain}.py`, `engine/src/seer_engine/llm.py`,
`web/lib/data.ts`, `web/lib/metrics.ts`, `web/app/(app)/positions/page.tsx`,
`web/app/(app)/leaderboard/page.tsx`, `web/scripts/seed-demo.mjs`,
`docs/handover/2026-10-04-paper-trading-ship.md`, `PAPER_TRADING_SHIP_PLAN.md`.

### Discovered Related Files
- `engine/src/seer_engine/strategies/a.py` (STRATEGY_A, AParams.as_dict, prepare/picks_prepared)
- `engine/src/seer_engine/strategies/base.py` (`Strategy` protocol, `History.upto`)
- `engine/src/seer_engine/backtest/book_runner.py:284` (`run_rules` → `run_backtest` for `DESIGN_V0`)
- `engine/src/seer_engine/backtest/runner.py:174-178` (`prepared is None` → `strategy.picks` per day)
- `engine/src/seer_engine/massive.py` (rate-limited client pattern: `MIN_INTERVAL`, injectable clock/sleep)
- `engine/src/seer_engine/http.py` (`redact`, `get_json`, `USER_AGENT`)
- `engine/src/seer_engine/config.py` (`get`, `require`, `.env.local` loading)
- `engine/src/seer_engine/cli.py` (commands auto-discovered from `commands/`)
- `engine/src/seer_engine/dates.py` (`run_dates`, `next_session`, `sessions`)
- `engine/src/seer_engine/demo.py` (`DEMO_TABLES`, `RESET_PAPER_CLOCK`)
- `engine/src/seer_engine/runs.py` (`real_run`)
- `db/migrations/001_init.sql`, `003_paper.sql`
- `engine/tests/test_migrate.py`, `test_paper_roster.py`, `test_strategy_purity.py`, `test_paper_command.py`, `test_paper_check.py`, `test_explain.py`, `test_llm.py`, `test_demo.py`
- `.github/workflows/nightly.yml`, `.env.example`
- `web/lib/strategy.ts` (`Gate`, `parseGate`), `web/components/roster.ts` (icon map incl. `gavel`),
  `web/app/(app)/leaderboard/view.ts` (`scoreOf`), `web/app/(app)/history/page.tsx`,
  `web/app/(app)/positions/positions.module.css`, `docs/design/Seer v2.dc.html`

---

## Current Dataflow

### Entry Point: the nightly job (`.github/workflows/nightly.yml`)
**Trigger:** cron `0 23 * * 1-5` (+ retry `0 1 * * 2-6`), `concurrency: seer-db-writer`,
`timeout-minutes: 45`. Steps: Check secrets → checkout → install → `migrate` → `nightly` → `paper` →
`paper_check` (id `paper_check`) → `explain` (`if: success() || steps.paper_check.outcome == 'failure'`,
`continue-on-error: true`, env `LLM_API_KEY/BASE_URL/MODEL` from secrets).
Only `DATABASE_URL_UNPOOLED` and `MASSIVE_API_KEY` are set as repo secrets today (handover §3).

### `paper` (`engine/src/seer_engine/commands/paper.py`)
1. `execute(conn, now, dry_run)` (`:107`): purge demo; `rd = dates.run_dates(now)`; requires
   `runs.real_run(conn, rd.session_date).status == "success"` else exit 1 (`:114-127`).
2. Reads `store.read_strategies` + `store.read_paper_state` per `roster.ROSTER` entry, rolled back
   (`:131-139`); `plan_night` (`:162`) checks digests (`store.check_digest`) and splits entries into
   `start` (no state) and `step` (last_session < rd.data_date).
3. `runs.start_paper` (own txn), then ONE transaction `_night` (`:296`): loads
   `store.load_market_window(conn, store.market_window_since(earliest))`, builds `_Tonight` (splits,
   dividends, cached `night_view`s), `_start` each new entry, then per engine `_step_bracket` /
   `_step_book` / `_step_benchmark`, then `runs.finish_paper`.
4. `_start` (`:343`): refuses when `_has_paper_rows` (orders, snapshots, book_* rows — `:330-337`);
   `store.freeze_spec(... spec, digest, backtest_gate, paper_start=rd.session_date)`;
   `store.init_paper_state`; bracket: `decide_bracket(new_portfolio(cash0), e.obj, e.params,
   view.history, members_on(rd.data_date), rd.data_date)` → `store.insert_pending_orders` →
   `store.write_pending(..., paper_start, decision=False)`.
5. `_step_bracket` (`:387`): per session S: `settle_bracket(pf, S, view.bars_on(S, held), splits,
   view.last_bar_date)` → `store.save_bracket_night` → `decide_bracket(night.portfolio, e.obj,
   e.params, view.history, members_on(S), S)` → `insert_pending_orders` → `write_pending(next_session(S))`.

**The only strategy-specific inputs are `e.obj` and `e.params`.** C plugs in by giving `decide_bracket`
a strategy object that already carries the stored verdicts for the sessions being decided.

### `decide_bracket` (`paper/bracket.py:162`)
`cut = {s: h.upto(data_date)}`; `picks = strategy.picks(cut, members, data_date, params)`;
`size_picks(pf, picks, next_session(data_date))`. Picks are portfolio-independent; sizing fills free
slots (`DESIGN_V0.max_positions = 4`, `time_stop = 5`) in rank order and rejects held symbols
without using a slot.

### `paper_check` (`commands/paper_check.py`)
One REPEATABLE READ, READ ONLY transaction (`check`, `:86`); `_check` reads heads + stored records;
`_expected(entry, head, market, dividends)` (`:218`) → `replay.expected_bracket(market, entry.obj,
entry.params, head)` for bracket entries, which runs `run_rules(fixed, strategy, params, DESIGN_V0,
start, last)` (picks path, `prepared=None`) and then `decide_bracket` for `next_session(last)`
(`replay.py:270-307`). C needs the verdict-carrying object here as well, read in the same txn.

### `explain` (`commands/explain.py`)
`_STRATEGIES_SQL` selects every strategy with `engine IN ('bracket','book')` that has a
`paper_state.pending_session`; `_BRACKET_SQL` reads pending orders without explanation. Nothing is
A-specific: C's pending orders are covered as soon as C has paper state. `prompt_for` uses the
row's `name`/`sub`.

### `llm.Client` (`llm.py`)
`complete(system, prompt)`: one non-streaming Messages POST to `messages_url(LLM_BASE_URL)` with
both `x-api-key` and `Authorization: Bearer`; body `{model, max_tokens, system, messages}` — **no
`temperature`, no `thinking` field**. Retries connection errors/429/5xx `retries` times with
backoff; `LlmError` otherwise; `_reply_text` joins `type == "text"` blocks and raises when none
(this is what happens when a reasoning model spends `max_tokens` on thinking — measured below).

### `massive.Client` (pattern for Finnhub)
`MIN_INTERVAL = 12.5` s spacing via injectable `clock`/`sleep`; key only in a query param; errors
pass through `http.redact`.

### Data Persistence
- `strategies` (001 + 003 columns `engine`, `rules_id`, `paper_start`; `params` jsonb holds the frozen
  spec C2 `{spec, digest, backtest_gate}`), `paper_state`, `orders` (`slot BETWEEN 1 AND 4`,
  `UNIQUE (strategy_id, session_date, symbol)`), `equity_snapshots`, `book_*`, `dividends`, `runs`.
- Migration 003 inserted the four roster rows and **deleted the unreferenced `B` and `C` rows**
  (`003_paper.sql` final statements) — so `004` must (re)insert `C`.
- `demo.DEMO_TABLES` lists every demo-owned table truncated by `purge_demo`.

### Exit Points
Web reads (`web/lib/data.ts`): `strategies()` (`ORDER BY sort, id`, `params->'backtest_gate'` →
`parseGate`), `positions`, `pendingOrders` (bracket branch is engine-driven), `closedTrades`,
`leaderboard`, `monthly`. Nothing reads verdicts today.

---

## Key Data Structures

### `RosterEntry` (`paper/roster.py`)
Fields `id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules, obj, object_name,
params, registry_id, lookback, gate_note`. `spec(e)` = `{id, engine, object, object_id,
registry_id, registry_digest, rules_id, rules, params: e.params.as_dict(), initial_idr}`;
`spec_text` canonical JSON; `spec_digest` sha256; `backtest_gate(e) = {"passed": False, "note":
e.gate_note}`; `strategy_params(e)` = `{spec, digest, backtest_gate}`. Digests pinned in
`tests/test_paper_roster.py::PINS` (SPY `ca309ea7…`, A `37cd89be…`, F4 `6c55c13a…`, F1 `e7fbb32d…`).

### `Strategy` protocol (`strategies/base.py`)
`id`, `lookback`, `picks(history, members, data_date, params)`, `prepare(history)`,
`picks_prepared(prepared, members, data_date, params)`; contract `picks_prepared(prepare(H)) ==
picks(H cut at d)`.

### `StrategyRow` (`paper/store.py`)
`id, name, engine, rules_id, is_champion, is_benchmark, sort, paper_start, params`.

### Web `Gate` (`web/lib/strategy.ts:87`)
`{ passed: boolean; note: string | null }`; `checklist(m, spy, gate)` (`web/lib/metrics.ts:47-72`)
6th row `'Backtest gate passed'`; `scoreOf(items, gatePassed)` (`leaderboard/view.ts:342-351`).

---

## Dependencies

### Configuration / Environment / External Services
- `FINNHUB_API_KEY` (in `.env.local`, listed in `.env.example:19`; not a repo secret).
- `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` (`.env.local`: GLM via z.ai, model `glm-5.3`; not repo secrets).
- Neon (`DATABASE_URL_UNPOOLED`), Finnhub REST, z.ai Anthropic-compatible Messages.

### Measurements (2026-10-04, this session)

| What | Result |
|---|---|
| Finnhub `company-news?symbol=MSFT&from=2026-10-01&to=2026-10-04` | 200 in 0.35 s, 147 items, keys `category, datetime, headline, id, image, related, source, summary, url`; avg headline 75 chars; 20 lean headlines (`id, datetime, source, headline`) = **3,115 bytes** of JSON |
| Finnhub `calendar/earnings?from&to&symbol=` (free key) | 200 in 0.3 s. `JPM` → 2026-10-13; `AAPL` → 2026-10-29 `amc`; `BRK.B` → returns the `BRK.A` row (2026-10-30); a week without a symbol → 86–116 rows. **Works per symbol on the free tier** |
| LLM `glm-5.3`, default body, `max_tokens=200` | 2 of 3 calls **failed**: `stop_reason='max_tokens'`, no text block (reasoning tokens ate the budget) |
| LLM, `max_tokens=1024` | 3/3 ok, 3.1–4.0 s |
| LLM, `max_tokens=2048` | 3/3 ok, 3.8–7.1 s |
| LLM, `temperature: 0`, `thinking: {"type": "disabled"}`, `max_tokens=300` | 3/3 ok, **1.6–1.7 s**, 431 input / ~36 output tokens, valid JSON verdict every time (a `thinking` block may still appear; the text block is present) |
| A's nightly pick count, Neon bars 2016-01-14..2026-10-02 (2,695 nights, `STRATEGY_A.picks_prepared` with `STRATEGY_A_PARAMS`, point-in-time members) | mean 24.3, **median 15**, p75 32, p90 58, p95 78, p99 137, max 250; 0 picks on 5.7 % of nights; **> 10 on 61.6 %**; > 4 on 78.4 %; capped at 10: 20,909 candidates = **≈ 163 per month (≈ 7.8 per night)** |

Time budget per night (cap 10): nominal 10 × (2 Finnhub calls ≈ 0.7 s incl. 1 s spacing ≈ 2 s +
LLM ≈ 2–4 s) ≈ **1 minute**. Worst case is bounded by the consecutive-failure stop (3 × (30 s timeout
+ 2 s backoff + 30 s) ≈ 3 min) and a step `timeout-minutes: 10`. The job's 45 minutes is
dominated by `nightly` (3 Massive calls per missing session at 12.5 s); one session ≈ 40 s.

Storage: ≈ 163 rows/month × (≈ 3.1 KB headlines + ≈ 0.3 KB other columns) ≈ **0.55 MB/month**,
≈ 6.6 MB/year — negligible on Neon's free 0.5 GB.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `ROSTER`, `RosterEntry`, `spec`, `backtest_gate`, `strategy_params` | `engine/src/seer_engine/paper/roster.py` | def | engine/paper |
| `PINS`, `test_display_fields_equal_the_migration_rows` | `engine/tests/test_paper_roster.py:41,76` | test | engine/tests |
| `test_repo_has_001_to_003`, `test_003_on_neon_flips_the_champion_and_drops_unreferenced_b_and_c` (`apply_migrations == ["003_paper.sql"]`) | `engine/tests/test_migrate.py:66,157` | test | engine/tests |
| `003` INSERT roster + `DELETE ... IN ('B','C')` | `db/migrations/003_paper.sql` (end) | config | db |
| `DEMO_TABLES`, `purge_demo` | `engine/src/seer_engine/demo.py:28,49` | def | engine |
| `decide_bracket` | `engine/src/seer_engine/paper/bracket.py:162` | def | engine/paper |
| `_start`, `_step_bracket`, `_has_paper_rows`, `_PAPER_ROWS_SQL` | `engine/src/seer_engine/commands/paper.py:330-400` | call | engine/commands |
| `_expected`, `_check` | `engine/src/seer_engine/commands/paper_check.py:111,218` | call | engine/commands |
| `expected_bracket` | `engine/src/seer_engine/paper/replay.py:270` | def | engine/paper |
| `_STRATEGIES_SQL`, `_BRACKET_SQL` | `engine/src/seer_engine/commands/explain.py` | call | engine/commands |
| `Client.complete` | `engine/src/seer_engine/llm.py` | def | engine |
| `massive.Client` (pattern) | `engine/src/seer_engine/massive.py:47` | def | engine |
| `FORBIDDEN_*`, `IMPURE` | `engine/tests/test_strategy_purity.py:23-27` | test | engine/tests |
| Veto/Explain steps | `.github/workflows/nightly.yml` | config | ci |
| `FINNHUB_API_KEY=` | `.env.example:19` | config | repo |
| `Gate`, `parseGate` | `web/lib/strategy.ts:87,98` | def | web/lib |
| `checklist` | `web/lib/metrics.ts:47-72` | def | web/lib |
| `scoreOf`, `CARD_BGS`, `LINES` | `web/app/(app)/leaderboard/view.ts:12-13,342` | def | web/app |
| `pendingOrders`, `strategies` | `web/lib/data.ts:60,247` | def | web/lib |
| orders section, `noOrders` | `web/app/(app)/positions/page.tsx:101-149` | def | web/app |
| icon map (`gavel` already mapped) | `web/components/roster.ts:5-15` | def | web/components |
| roster fixtures (4 rows) | `web/components/roster.test.ts:5-10`, `web/app/(app)/leaderboard/view.test.ts:7-13` | test | web |
| roster array, A's orders with `'A'` literal, TRUNCATE | `web/scripts/seed-demo.mjs:50-68,168-282` | config | web/scripts |
| P6 entry, "Later" | `docs/ROADMAP.md:91` | doc | docs |
| `paper`, `paper_check`, `explain`, `llm`, `paper (P4)` sections | `engine/package_readme.md:375-406,1296-1361` | doc | engine |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/strategies/c.py` (new) — C object, params, candidates, prompt, parser. Phase 1.
2. `engine/tests/test_strategy_c.py` (new). Phase 1.
3. `db/migrations/004_news_veto.sql` (new). Phase 2.
4. `engine/src/seer_engine/paper/roster.py` — entry `C`, `backtest_gate` "not applicable". Phase 2.
5. `engine/src/seer_engine/paper/store.py` — `NewsVerdict`, `write_vetoes`, `read_vetoes`, `has_vetoes`, `allowed_between`. Phase 2.
6. `engine/src/seer_engine/demo.py` — `news_vetoes` demo-owned. Phase 2.
7. `engine/tests/test_paper_roster.py`, `test_migrate.py`, `test_demo.py`, `test_paper_store.py` (or new `test_paper_store_vetoes.py`). Phase 2.
8. `engine/src/seer_engine/finnhub.py` (new), `engine/src/seer_engine/llm.py` (`temperature`, `thinking`), `engine/tests/test_finnhub.py` (new), `test_llm.py`. Phase 3.
9. `engine/src/seer_engine/commands/veto.py` (new), `engine/tests/test_veto_command.py` (new). Phase 4.
10. `engine/src/seer_engine/commands/paper.py`, `commands/paper_check.py`, tests `test_paper_command.py` / `test_paper_check.py` / `test_explain.py` (C cases). Phase 5.
11. `web/lib/strategy.ts`, `web/lib/metrics.ts`, `web/lib/data.ts`, `web/app/(app)/leaderboard/view.ts` + `page.tsx`, `web/app/(app)/positions/page.tsx` + `positions.module.css`, `web/scripts/seed-demo.mjs`, web tests. Phase 6.
12. `.github/workflows/nightly.yml`, `engine/package_readme.md`, `docs/runbooks/paper-trading.md`, `docs/ROADMAP.md`. Phase 7.

**This document describes. The plan files prescribe.**

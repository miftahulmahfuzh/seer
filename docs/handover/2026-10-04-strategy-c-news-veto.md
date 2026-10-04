# Handover: Strategy C, A's candidates with a news + LLM veto, on paper (roadmap P6, v0.2.0)

Written 2026-10-04, after the paper-trading set landed on `main` @ `320c287` (pruned at `c69bd82`).
The nightly paper clock starts with the first scheduled run after that merge (expected first paper
session: Tue 2026-10-06). The `v0.1.0` release waits for its 5-night check and is **not** part of
this handover (see §1).

Pass this file straight to `/analyze` in a fresh session, and read all of it first. Like the
earlier handovers, it separates:
- decisions that are **already made**;
- facts that were **verified**;
- questions the analysis still has to settle.

---

## 0. In plain words

Design §4 names three strategies. A and its rework failed their backtest gates; B (the ML ranker)
failed its gate too. **C** has never been built. C is A with a second opinion: every night it takes
the stocks A would buy for the next session, reads the latest news about each one (Finnhub), and
asks the LLM whether the news says "don't touch this right now" (an earnings miss, fraud, a
lawsuit, a buyout, a guidance cut...). C buys only what the LLM lets through. If the news or the
LLM can't be reached, C does **not** buy (design §8: "a failed veto check is no trade").

C can only be tested going forward: an LLM has read the news of the past, so a backtest of C would
be contaminated (design §4). So C joins the paper roster next to A, and the app shows, month by
month, whether the veto made A better or worse. Nothing here moves real money.

---

## 1. Where we are

| Item | State |
|---|---|
| P4 nightly paper trading | Code landed 2026-10-04 (`PAPER_TRADING_SHIP_PLAN.md`, 13 phases). Roster `SPY` (champion), `A`, `F4-MOM12-N20-TREND`, `F1-SPY-SMA200-M`. Nightly steps Nightly → Paper → Paper check → Explain |
| v0.1.0 | Pending the operational check: ≥ 5 paper sessions, `paper_check --require-sessions 5` green on Neon, then README, then `gh release create v0.1.0` ([runbook release checklist](../runbooks/paper-trading.md#release-checklist-v010)). **Not this handover's work** |
| P6 Strategy B | Failed P6a. `STRATEGY_B_FROZEN = None`, no model committed (`tests/test_strategy_b_frozen.py` enforces that). Closed record |
| P6 Strategy C | **Not started. This handover** |
| LLM client | `engine/src/seer_engine/llm.py` (Anthropic-compatible Messages API, both `x-api-key` and `Authorization: Bearer`, timeout, retry, redaction) and the `explain` command already exist |

Read before planning:
- `docs/plans/2026-10-03-seer-design.md`: all of it. **§1 stays law.** §4 (C's row), §8 (LLM failure → no trade).
- `docs/ROADMAP.md`: P4, P6, "Later".
- `docs/runbooks/paper-trading.md`: all of it (the night, frozen specs, replay check, owner steps).
- `engine/package_readme.md`: `paper/*`, `commands/paper`, `paper_check`, `explain`, `llm`, `strategies` (A).
- `engine/src/seer_engine/paper/roster.py`, `paper/bracket.py`, `paper/replay.py`, `paper/store.py`, `commands/paper.py`, `commands/paper_check.py`, `commands/explain.py`, `llm.py`.
- `web/lib/data.ts`, `web/lib/metrics.ts`, `web/app/(app)/positions/page.tsx`, `web/app/(app)/leaderboard/page.tsx`, `web/scripts/seed-demo.mjs`.
- `docs/handover/2026-10-04-paper-trading-ship.md` (the decisions C must not break) and `PAPER_TRADING_SHIP_PLAN.md` (its Decisions table).

---

## 2. Decisions

### Law: do not reopen

| Topic | Rule |
|---|---|
| Go-live | Design §1, unchanged. C never presents anything as a real-money buy. Today keeps "SPY buy-and-hold is the champion; Seer recommends no buys" |
| Same code path | C is a bracket strategy under `DESIGN_V0`: its picks are A's ranked picks (same `STRATEGY_A`, same `STRATEGY_A_PARAMS`, same history) minus the vetoed symbols, then `sim.size_picks` + `sim.step` through `paper/bracket.py`. No new fill, sizing or exit logic |
| The existing roster is frozen | `SPY`, `A`, `F4-MOM12-N20-TREND`, `F1-SPY-SMA200-M` keep their ids, specs and digests byte for byte. Their paper clocks must not reset. `paper_check` stays green for them throughout |
| Closed records | `backtest/registry.py`, the runners, `docs/backtests/*`, `STRATEGY_A_PARAMS`, `STRATEGY_A2_PARAMS`, `STRATEGY_B_FROZEN` are not edited |
| No look-ahead | C's decision for session S uses bars through `prev_session(S)` and news published before the veto run's own start time (the night before S). Nothing published after the decision is ever read for it |
| Reproducible replay | The LLM is not re-asked during a replay. Every verdict and the news it saw are stored; `paper_check` replays C from the stored verdicts |
| Read-only UI, Seer v2 design, icon-only buttons, honest reporting | As in the previous handovers |

### Decided by this handover (each can be overturned by a one-line change before planning)

| # | Topic | Decision | Why |
|---|---|---|---|
| D1 | **C's id and clock** | New roster entry `C` (`C · News veto`, sub "A's picks, LLM can veto on news", icon `gavel`), engine `bracket`, rules `design-v0`, sort 5. Its own `paper_start` = the first night it runs after landing (D4 of the previous handover: a new id has its own clock) | The other four clocks are untouched |
| D2 | **Candidates** | Each night, A's ranked picks for the next session (exactly what `decide_bracket` would hand A), up to the first **10**. Ranks beyond 10 are not checked and not bought | Bounds the nightly cost (≤ 10 news calls + ≤ 10 LLM calls) while leaving room for vetoes to be refilled by lower ranks |
| D3 | **News** | Finnhub `GET /api/v1/company-news?symbol=<dot form>&from=<run date − 3 days>&to=<run date>` (ET dates), keep items with `datetime` < the veto run's start, newest first, at most 20 headlines (+ summary, source, time). Zero items is a valid input ("no news") | Free tier verified (§3); 72 hours covers a weekend |
| D4 | **Verdict** | One LLM call per candidate with a frozen system prompt (`PROMPT_VERSION = "c-veto-v1"`), temperature 0, answer as JSON `{"verdict": "allow" | "veto", "reason": "<one sentence>"}`. Anything else (timeout, HTTP error, no LLM config, unparsable JSON, no Finnhub key, Finnhub error) is verdict **`failed`**, which is **no trade** (design §8) | Design §4/§8 |
| D5 | **Frozen spec** | C's spec (digest) includes A's spec, the candidate cap, the news window and cap, `PROMPT_VERSION` and the prompt text, and the LLM model name it was started with. If the configured `LLM_MODEL` differs from the frozen one, every verdict that night is `failed` (no trades) and the UI says so. It never fails the night for the other strategies, and never silently resets C's clock | D4 of the previous handover (a change is a new id) without letting one key break the whole night |
| D6 | **Where the LLM runs** | A new command `veto`, run after `nightly` and **before** `paper`, outside `paper`'s transaction. It computes A's ranked candidates for `run_dates(now).session_date` from Neon (pure path), fetches news, asks the LLM, and stores one row per candidate. Workflow step `continue-on-error: true`. `paper` then decides C from the stored verdicts; a candidate with no stored verdict counts as `failed` | `paper` stays one fast transaction with no network; a broken veto step can only make C sit out, never break the night |
| D7 | **Persistence** | Migration `004`: a `news_vetoes` table, one row per (strategy, session, candidate): rank, symbol, verdict (`allow`/`veto`/`failed`), reason, model, prompt version, the headlines seen (jsonb: id, datetime, source, headline; no summaries, to stay lean), decided_at. Plus the roster row for `C` (the `003` delete removed the old `C` row) | Replay needs the stored inputs; Neon free tier |
| D8 | **Replay check** | `paper_check` replays C with `run_rules(DESIGN_V0)` on a strategy object built from A plus the stored verdicts (veto and failed removed, missing = failed), and compares as it does for A | Same proof as the rest of the roster |
| D9 | **Go-live checklist for C** | Design §1 item 5 says the backtest item applies to quant strategies only. C's sixth row reads "Backtest gate: not applicable (LLM strategy, design §1 item 5)" and counts as **not passed** in the score; the score line says real money for C would need an explicit owner decision even if the other five pass | Proof before money; changing that is the owner's call (ROADMAP P6a note (d)) |
| D10 | **UI** | C appears everywhere the roster does (Positions switcher, History filter, Leaderboard cards, Month by month, checklist). Positions for C adds a "Vetoed tonight" list (symbol, verdict, the one-line reason, headline count) under its paper orders. Today unchanged | The owner wants to see what the veto did |
| D11 | **B** | Stays off the paper roster: failed P6a, no committed model, closed record. The ROADMAP's P6 "Done when" is reworded to "A and C each have an independent paper portfolio; B failed P6a and is closed" | Closed records law |
| D12 | **Secrets** | `FINNHUB_API_KEY`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` as GitHub repo secrets are **owner steps** in the runbook (none is set today, §3). Until they are set, C runs with every verdict `failed` and makes no trades, and the UI says why | Handover convention: owner steps are documented, not done |

---

## 3. Verified facts (2026-10-04): trust these

- `main` @ `c69bd82` (the paper-trading set merged at `320c287`).
- **Finnhub** (key `FINNHUB_API_KEY` in `.env.local`): `company-news?symbol=AAPL&from=2026-09-28&to=2026-10-02` → HTTP 200, 242 items, fields include `datetime` (unix seconds), `headline`, `source`, `summary`; headers `X-Ratelimit-Limit: 60`, `X-Ratelimit-Remaining: 59`. `symbol=BRK.B` (dot form, as stored in `bars`) → 52 items.
- **GitHub repo secrets set:** only `DATABASE_URL_UNPOOLED`, `MASSIVE_API_KEY`. `LLM_*` and `FINNHUB_API_KEY` are **not** set.
- **LLM**: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` exist in `.env.local` (GLM via z.ai, Anthropic-compatible). `seer_engine.llm.Client` exists; `explain` writes NULL on failure and exits 0.
- **Roster code**: `paper/roster.py` `ROSTER` is a tuple of `RosterEntry` (id, display fields, engine, rules, obj, object_name, params, registry_id, lookback, gate_note); `strategy_params(e)` / `spec_digest` produce the frozen spec; `paper` raises `SpecMismatch` for a started id whose digest changed.
- **Schema**: migration `003` deleted the `B` and `C` `strategies` rows on Neon (unreferenced). `orders.explanation` and `book_targets.explanation` exist.
- A's candidate count per night is small (the P3 backtest's `size_picks` rejections show the ranked list often exceeds the 4 free slots; the cap of 10 is a bound, not a measurement). **The analysis measures** the distribution of A's nightly pick count on Neon's 2015–2026 bars and states it.

---

## 4. Scope

**In scope:**
1. **Engine, pure:** a C strategy object (A's picks filtered by a verdict map, `Strategy` protocol, pure), the roster entry `C` with its frozen spec (D5), and the prompt text + JSON verdict parser (pure).
2. **Engine, impure:** `finnhub.py` client (rate-limited ≤ 60/min, redacted errors, injectable transport), the `veto` command (D6), migration `004` (D7), store read/write for verdicts, `paper` deciding C from stored verdicts, `paper_check` replaying C (D8), `explain` covering C's pending orders like A's.
3. **Workflow:** `nightly.yml` gains the `Veto` step between `Nightly` and `Paper` (`continue-on-error: true`; env `FINNHUB_API_KEY`, `LLM_*` from secrets). Check the job's 45-minute budget.
4. **Web:** C in every roster view; the "Vetoed tonight" list on Positions; the checklist's D9 row; the demo seed with a C portfolio and some verdict rows.
5. **Docs:** `engine/package_readme.md`, `docs/runbooks/paper-trading.md` (the veto step, failure states, owner steps for the two new secrets, C's clock), `docs/ROADMAP.md` (P6 entry with D11's wording).

**Out of scope:** real money; editing design §1; B; new quant strategies or registry appends; changing A, F4, F1 or SPY; the `v0.1.0` release; notifications; the trade journal; backtesting C.

---

## 5. Acceptance criteria

1. **Non-regression.** The four existing roster entries' digests are byte-identical; their `paper_state`, orders, book rows and snapshots are untouched by the migration and by C's first night; `paper_check` stays green for them.
2. **Same path.** On synthetic data, C's nightly state after ≥ 5 nights equals the `run_rules(DESIGN_V0)` replay from stored verdicts; with every verdict `allow`, C's orders equal A's on the same nights.
3. **Failure = no trade.** Tests cover: no LLM config; LLM timeout/HTTP error; unparsable reply; Finnhub error; missing verdict row; frozen-model mismatch. Each gives no C order for that candidate and never fails `paper` or the other strategies.
4. **No look-ahead.** News items dated at or after the veto run's start are never sent; bars dated ≥ S never change S's candidates.
5. **Idempotency.** Re-running `veto` for a session that already has verdicts makes no new LLM or Finnhub calls and writes nothing; `paper` re-runs write nothing.
6. **UI.** C renders in Positions (with "Vetoed tonight"), History, Leaderboard, Month by month and the checklist (D9 row), at 414 pt and desktop, light and dark, Seer v2 design, icon-only buttons. Today still shows no buys.
7. **CI** green: engine tests 0 skipped, ruff, web vitest and `tsc --noEmit`.
8. **Docs** updated as in §4.5, including the owner steps for `FINNHUB_API_KEY` and `LLM_*`.

---

## 6. Open questions for the analysis to settle (recommend, don't ask)

- **The prompt.** Write `c-veto-v1` in full: what counts as a veto (event risk in the next ~5 sessions: earnings within the window, guidance cut, accounting/fraud, legal/regulatory action, M&A news, trading halt, major downgrade), what does not (generic market news, price-move recaps), and the exact JSON contract. Keep it short; it is frozen into C's digest.
- **Earnings dates.** Finnhub's free `calendar/earnings` might give upcoming earnings directly. Verify it on the free key; if it works, decide whether the veto gets "earnings within the next 5 sessions" as a fact in the prompt (part of the frozen spec) or stays news-only.
- **Rate limits and the time budget.** ≤ 10 Finnhub calls (60/min) and ≤ 10 LLM calls per night; measure an LLM call against z.ai and confirm the Veto step fits inside the nightly job's 45 minutes with the existing steps.
- **Where the candidates are computed.** `veto` needs A's ranked picks for the next session before `paper` runs. Reuse `paper`'s windowed market load and `decide_bracket`'s pick call without duplicating them; on a catch-up night (several sessions in one run) decide what `veto` does for the earlier sessions (recommended: verdicts only for the newest session; earlier ones have none, so C sits them out, and the runbook says so).
- **Storage size.** Estimate `news_vetoes` growth per month with headlines only; confirm it is negligible on the Neon free tier.
- **Phase split.** Small phases as before: migration + roster entry; pure C strategy + prompt/parser; Finnhub client; `veto` command; `paper`/`paper_check`/`explain` integration; web; ship (workflow step, docs).

---

## 7. Environment

Unchanged from `docs/handover/2026-10-04-paper-trading-ship.md` §7:
- WSL2 Ubuntu, zsh, Python 3.11. A worktree needs its own `engine/.venv`:
  `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`.
- Engine tests: `docker start seer-pg`, then
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`. 0 skipped.
- Web: `cd web && npm ci && npx vitest run && npx tsc --noEmit`.
- Real runs: `SEER_ENV_FILE=/home/miftah/seer/.env.local`; never `source` it (the database URL has an unquoted `&`).
- Never print a secret. Plain `vercel ls` prints the Vercel token; don't run it.
- Owner steps (secrets) go into the runbook; the pipeline does not set them.
- The repo is public on purpose; paper losses and vetoes that cost money are shown too.

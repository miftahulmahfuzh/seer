# Seer Roadmap — v0.1.0 major plans

Design: [docs/plans/2026-10-03-seer-design.md](plans/2026-10-03-seer-design.md)

v0.1.0 goal: **Seer's frozen paper roster (SPY champion, A, F4, F1) trading on paper every night,
shown month by month next to SPY, on the phone.** Paper only (owner option (b), 2026-10-04): real
money is out of scope; design §1 is unchanged, and no strategy has passed a backtest gate.

## P0 — Foundations · done 2026-10-04 (CI: `ruff check` + engine pytest, `tsc --noEmit` + web vitest on every push)
- Repo layout: `web/` (Next.js), `engine/` (Python), `.github/workflows/`
- `.gitignore`, `.env.example`; rotate any secrets that were ever exposed
- Neon schema + migrations (tables from design §7)
- Accounts: Massive, Google OAuth, Finnhub, LLM, Vercel, Neon: all verified 2026-10-03
- **Done when:** schema migrated on Neon, CI runs lint + tests on push

## P1 — Data pipeline · done 2026-10-03 locally on Neon (backfill + nightly, [runbook](runbooks/data-pipeline.md)); pushed, Actions schedule awaits repo secrets
- Point-in-time S&P 500 ∪ Nasdaq-100 membership
- Backfill 10+ years of split-adjusted daily bars via yfinance (Massive free tier only reaches ~2 years back); nightly incremental fetch via Massive grouped-daily
- Market calendar (holidays, half days)
- **Done when:** nightly job keeps `bars` current for the whole universe, idempotent re-runs

## P2 — Fill simulator (critical path) · done 2026-10-03 on synthetic bars (`engine/src/seer_engine/sim/`, API in [engine/package_readme.md](../engine/package_readme.md)); P3/P4 wire it in
- Order lifecycle exactly as design §5 (strict fill, SL-first, gaps, time stop, costs)
- Whole-share sizing, 4 slots, equity ÷ 4
- Exhaustive unit tests on synthetic bars
- **Done when:** every edge case in design §5 has a passing test

## P3 — Strategy A + backtest · done 2026-10-03: **Gate failed — rework before P4; P4 must not start** ([report](backtests/2026-10-02-strategy-a.md))
- Implement Strategy A on the shared simulator
- 10-year backtest vs SPY; tune parameters on early years, validate on later years
  (no tuning on the validation window), then freeze parameters
- Backtest report: equity curve, return, win rate, profit factor, max drawdown
- **Gate:** if A cannot beat SPY in backtest, rework before P4. Don't paper-trade a loser.
- **Verdict (2026-10-02 data, out-of-sample 2022-01-03 → 2026-10-02):** Strategy A fails the P3 gate: out of sample it returned −15.0% against +71.9% for total-return SPY, with profit factor 0.92 and max drawdown 33.3%, so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; P4 must not start until Strategy A is reworked.

## P3b — Strategy A rework under walk-forward · done 2026-10-03: **Gate failed — Strategy A's one rework failed; P4 stays blocked** ([report](backtests/2026-10-02-strategy-a2-walkforward.md))
- Spec: [handover](handover/2026-10-03-strategy-a-rework.md). The 2022-01-03 → 2026-10-02 window was burned by P3, so validation is an anchored yearly walk-forward: tune on 2015-10-19 → the end of Y−1, trade Y, 2018 → 2026-10-02, as one continuous portfolio
- Tried, all pre-registered: V0 `control` (v1), V1 `regime` (no new picks when SPY ≤ its SMA(200)), V2 `regime_calm` (rank by ATR/close), V3 `regime_calm_floor` (close ≥ $10) × P3's 81-run grid = 324 combinations per fold, selected by P3's rule; every variant's own walk-forward is in the report too
- **Gate:** the walk-forward curve must beat total-return SPY over the same span with PF ≥ 1.3 and max DD ≤ 15%
- **Verdict (2026-10-02 data, walk-forward 2018-01-02 → 2026-10-02):** Strategy A2 fails the P3b gate: walk-forward from 2018-01-02 to 2026-10-02 it returned +9.1% against +187.6% for total-return SPY, with profit factor 1.02 and max drawdown 29.1%, so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; Strategy A's one rework has failed, and P4 stays blocked.
- Strategy A's one rework failed. Strategy A is not reworked again on this data, `STRATEGY_A2_PARAMS` stays `None`, and P4 stays blocked. The owner decides next (handover §8):
  - (a) go to P6's Strategy B (ML ranker), validated with the same walk-forward machinery;
  - (b) accept SPY buy-and-hold as the honest champion for now: paper-trade research strategies, and recommend no real-money picks;
  - (c) revisit a design-§5 trade rule (for example the 5-day time stop or the 4 slots). That is a design change, and it needs the owner's explicit decision and a new handover; it is never done inside a rework.

## P6a — Strategy B (ML ranker) under walk-forward · done 2026-10-03: **Gate failed — B's one round failed on this data; P4 stays blocked** ([report](backtests/2026-10-02-strategy-b-walkforward.md))
- Spec: [handover](handover/2026-10-03-strategy-b-ranker.md). Option (a) of the P3b verdict, run ahead of P4. Research-only and read-only; no trade rule changed
- Tried, all pre-registered before any B result: gradient-boosted regression trees (fixed hyperparameters, no search) on 15 cross-sectional feature ranks + 3 raw SPY features, trained per fold on the net-of-cost return of A's fixed bracket order, purged at each fold's tuning end; picks are every candidate with a predicted net return > 0, so B may sit a night out. B-linear (ridge) ran beside it as information only. P3b's folds, one continuous portfolio 2018-01-02 → 2026-10-02, with A2 on the same chart
- Determinism probe on the last fold: bit-identical at 1 thread and at the default, so B is gated
- **Gate:** the walk-forward curve must beat total-return SPY over the same span with PF ≥ 1.3 and max DD ≤ 15%
- **Verdict (2026-10-02 data, walk-forward 2018-01-02 → 2026-10-02):** Strategy B fails the P6a gate: walk-forward from 2018-01-02 to 2026-10-02 it returned +13.3% against +187.6% for total-return SPY, with profit factor 1.03 and max drawdown 57.6%, so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; Strategy B's one round has failed on this data, and P4 stays blocked.
- B's one round failed on this data; P4 stays blocked. B is not reworked on this data, `STRATEGY_B_FROZEN` stays `None`, and no model is committed. The owner decides next (handover §8):
  - (b) accept SPY buy-and-hold as the honest champion for now: Seer can still paper-trade research strategies (P4 without real-money picks), and the home screen recommends no buys;
  - (c) revisit a design-§5 trade rule (for example the 5-day time stop, the 4 slots, or a longer holding horizon). That is a design change: it needs the owner's explicit decision and a new handover, and it is never done inside a strategy phase;
  - (d) Strategy C (news + LLM veto) is forward-paper only by design §4, so it cannot pass a backtest gate and does not unblock P4 under the current ROADMAP wording; changing that wording is the owner's call.

## P7a — Trade rules as a value + dev-window strategy search · done 2026-10-04: **None eligible on the dev window — P7b does not run; P4 stays blocked** ([report](backtests/2026-10-04-p7a-dev-exploration.md), [pre-registration](plans/2026-10-04-p7b-preregistration.md))
- Spec: [handover](handover/2026-10-03-trade-rules-revision.md). The owner's option (c) of the P6a verdict: design §5 became a parameter. Design §1 is unchanged, and design §5 itself is not edited (D10): any revision is proposed only in the pre-registration file
- Rules as a value: `TradeRules`, with `DESIGN_V0` reproducing §5 exactly. A, A2 and B re-render byte-identically: re-running `backtest`, `backtest_wf` and `backtest_b` on the unchanged Neon data (1,817,429 bar rows through 2026-10-02): all 11 `docs/backtests/2026-10-02-*` files `cmp`-equal (phase 13, 2026-10-04)
- Data: a local, gitignored research store (never Neon) of 2,490,793 bar rows, 539 of 1,061 symbols served (522 members unserved, so single-stock results are optimistic, D4), 28,206 dividends, fingerprint `5451195fd552`. Development window only: each candidate's first session with enough history → 2015-10-16, enforced in code. No P7a number comes from a later session
- Tried, all pre-registered in `backtest/registry.py` (committed at `b2ec090` and pushed before the run): **54 candidates** across 11 families (F1–F7, F9–F11 and two references), 11 of them needing owner inputs. Each was judged against total-return SPY on its own window, and the report shows every row, the frontier and a deflated-Sharpe multiple-testing note
- Finalist rule (D8, written before any result): eligible = beats total-return SPY, max DD ≤ 15%, PF ≥ 1.3, ≥ 100 closed trades and no owner input; rank by CAGR ÷ max DD; top 3, at most one per family
- **Result (dev window, ≤ 2015-10-16):** none eligible. Of 54 candidates, 35 beat total-return SPY, 0 kept max DD ≤ 15%, 40 reached PF ≥ 1.3, 33 made ≥ 100 trades and 43 needed no owner input; none met all five. Best MAR: `F4-MOM12-N20-TREND` (F4), CAGR +16.2% vs +7.9%, max DD 22.2%, PF 2.27, 1,154 trades; it failed on max DD ≤ 15%
- The frontier in the report shows what drawdown was reachable at a SPY-beating return on 1993–2015 data. That is the evidence for the owner's next decision
- **Real money (owner facts, handover §3):** the owner's plan to put 20,000,000 IDR in on 2026-11-01 conflicts with design §1, which is not moved. Real money needs a strategy that has passed the backtest gate **and** ≥ 3 months plus ≥ 100 closed trades of forward paper. As of 2026-10-04 none has passed and P4 has not started, and with no finalist there is no §1-compliant real-money date yet. The earliest would be about 3 months after some future passing strategy's paper trading starts. The owner remains free to put the money into SPY itself on 2026-11-01; that is the benchmark and needs no Seer approval

## P7b — Run the pre-registered finalists once on the test window · not run: none eligible
- P7a found no candidate eligible under D8 on the dev window, so P7b does not run and no P7a candidate touches the test window 2015-10-19 → data end ([pre-registration](plans/2026-10-04-p7b-preregistration.md) records "none eligible"). Design §5 is not edited (D10)
- The owner decides next with the [dev frontier](backtests/2026-10-04-p7a-dev-exploration-frontier.svg) in hand (handover §9):
  - (b) accept SPY buy-and-hold as the honest champion: Seer can still paper-trade research strategies (P4 without real-money picks), and the home screen recommends no buys;
  - a §1 discussion, with the frontier as the evidence of what drawdown was reachable at a SPY-beating return;
  - new ideas appended to the registry under D6 (each committed before its dev run, every try reported) in a new handover; the answers to the owner-input questions (ETFs, fractional shares, market-on-open, fees, leverage, T-bills) may make more candidates eligible

## P8 — Method lab + Sera · lab running since 2026-10-04 (no method eligible yet); Sera site at [seertrade.site/sera](https://seertrade.site/sera) ([design](plans/2026-10-04-method-lab-design.md))
- The search goes on after P7a as a **method lab**: `lab/lab.sqlite`, a committed SQLite file (never Neon) with tables `methods`, `trials` (each with its month-end equity curve), `ideas_seen` and `insights`. Trials and insights are append-only (triggers). It was seeded with P7a's 54 trials as 14 historical methods (`H-*`), and every new trial counts toward N, the number of tries that deflates each result (DSR ≥ 0.90 at N joins the five D8 hurdles — 0.95 until the owner set the bar to 0.90 on 2026-10-07, method-lab design §7.1). Access: `engine/src/seer_engine/lab/store.py`; CLI: `python -m seer_engine lab …`; schema v2 adds the `synthesis` insight kind
- A method is one pre-registered file, `engine/src/seer_engine/lab/methods/mNNNN_<slug>.py`, committed and pushed before `lab run` touches the dev window (1993 → 2015-10-16). The test window (2015-10-19 → today) is spent one counted look at a time, only through promotion of a `dev-eligible` method. Design §1 and the D8 hurdles do not move
- Two skills, **no human in the loop**: `/explore-and-experiment-new-method` explores one idea end to end (pre-register, run, plain-language analysis ending in "My opinion:", at least one insight, at least one queued idea). `/sera-the-explorer <n>` runs n of them in parallel (at most 4 at a time, one worktree and tmux window each), promotes eligible methods herself, and closes each batch with one `synthesis` insight
- **M0001** (momentum scaled by its own realized volatility, 4 variants): the first lab trials to pass max DD ≤ 15%, PF ≥ 1.3 and ≥ 100 trades together (best `M0001-TV12`: max DD 12.9%, PF 2.27, 1,130 trades). They failed only on beating SPY: CAGR 7.6% vs total-return SPY 7.9%, DSR 0.90 at N = 58. Rejected; M0002 and M0003 (asymmetric and dynamic momentum scaling) queued
- **Sera site** (`/sera`, desktop-first, private to `mahfuzh74@gmail.com`; any other account gets a 404): Overview (latest synthesis, every trial against the gate, hurdle funnel, progress, luck bar, families), Methods and one page per method (charts vs SPY, the analysis and opinion, every trial's detail), Journal, Ideas and How it works. It reads `web/data/lab.json`, which `lab stage` regenerates under the database's write lock and stages with it on every lab commit; Vercel deploys it on the push to `main`. CI runs on `lab/**` and an engine test fails any commit whose JSON does not match its database
- **Done when:** never, by design: the lab keeps searching. It feeds P7b-style test looks and the paper roster only through promotion

## P4 — Nightly forward paper trading · paper-only (owner option (b), 2026-10-04); no real-money recommendations; §1 unchanged · code landed 2026-10-04; the clock starts with the first scheduled nightly after the merge ([runbook](runbooks/paper-trading.md))
- Spec: [handover](handover/2026-10-04-paper-trading-ship.md). Plan: `PAPER_TRADING_SHIP_PLAN.md` (13 phases)
- Roster, frozen before any result (D1, D4): `SPY` (buy and hold, dividends reinvested; the champion), `A` (`STRATEGY_A_PARAMS`, design-v0 brackets), `F4-MOM12-N20-TREND` and `F1-SPY-SMA200-M` (P7a registry, monthly-hold book rules). Each starts from 20,000,000 IDR on the same first paper day; a changed strategy gets a new id and its own clock
- What landed: migration 003 (`paper_state`, `book_positions`, `book_targets`, `book_fills`, `book_trades`, `dividends`, roster rows with SPY as champion); pure night functions in `engine/src/seer_engine/paper/` that mirror the runner loop bodies (bracket, book, benchmark), plus a book-engine split rule; Massive dividends and held-symbol bars in `nightly`; the `paper` command (one transaction per night, idempotent per session, `runs.paper_status`); the `paper_check` replay check against `run_rules` / `buy_and_hold`; optional `explain` (LLM); nightly steps Paper → Paper check → Explain; the web: SPY-champion Today with no buys, paper labels, book positions and trades, Month by month, an honest six-row go-live checklist
- Neon at migration 003 since 2026-10-04; a rolled-back night on real data succeeded ([runbook ship check](runbooks/paper-trading.md#ship-check--2026-10-04))
- No look-ahead: decisions for session S read data through `prev_session(S)` only; stale data or a failed bars run means no paper step and the "do not trade" screen
- **Done when:** 5 consecutive trading days run unattended with correct settlement, proven by `paper_check --require-sessions 5` on Neon and checked in the run logs and the app. Pending: needs 5 live sessions after the merge

## P5 — Web app · done 2026-10-03 on demo data; live at [seertrade.site](https://seertrade.site) (Vercel Git integration: every push to `main` deploys production; domain verified 2026-10-04: `/` 307 → `/signin`, manifest and auth providers 200); paper views land with P4
- Implement the Claude Design output: Sign-in, Today, Positions, Leaderboard, History
- Auth.js, Google only, single `ALLOWED_EMAIL`
- PWA manifest + apple-touch-icon; Lucide icon-only buttons
- Deploy to Vercel, connect seertrade.site: done. The paper-trading build was proven as a preview deploy on 2026-10-04 and reaches production with the merge
- Paper-only additions (P4 set): Today shows "SPY buy-and-hold is the champion; Seer recommends no buys"; research orders and positions labelled paper; Month by month on the Leaderboard; checklist row "Backtest gate passed"
- Owner checks left ([runbook](runbooks/paper-trading.md#owner-steps)): the Google OAuth redirect URI for seertrade.site and a sign-in from the XS Max, Add to Home Screen, and the `FINNHUB_API_KEY` and `LLM_*` repo secrets (optional for the night; Strategy C trades only with them)
- **Done when:** usable from the XS Max home screen; picks copyable into Gotrade (for the paper-only ship: the paper views readable on the phone)

## P6 — Challengers · B closed (failed P6a); C code landed 2026-10-04, on paper from the first scheduled nightly after the merge ([runbook](runbooks/paper-trading.md#strategy-c-the-news-check))
- Strategy B (ML ranker): walk-forward backtest failed P6a (above). Closed record: `STRATEGY_B_FROZEN = None`, no committed model, not on the paper roster (D11)
- Strategy C (Finnhub news + LLM veto on A's candidates), forward paper only: a backtest of an LLM on past news is contaminated (design §4). Spec: [handover](handover/2026-10-04-strategy-c-news-veto.md). Plan: `STRATEGY_C_NEWS_VETO_PLAN.md` (7 phases)
  - Each night the new Veto step takes A's first 10 ranked candidates for the next session, reads up to 20 Finnhub headlines from the last 3 days published before the step started plus the earnings dates in the 5-session window, and asks the LLM for `allow` or `veto` under the frozen prompt `c-veto-v1` and model `glm-5.3`. C buys A's candidates minus everything not allowed, through the same `DESIGN_V0` brackets as A
  - Any failure (missing secret, Finnhub or LLM error, unparsable reply, another `LLM_MODEL`) is a `failed` verdict: no trade (design §8), never a failed night
  - Verdicts and the headlines seen are stored in `news_vetoes` (migration 004); `paper_check` replays C from them and never re-asks the LLM
  - Backtest gate: not applicable (LLM strategy, design §1 item 5); the checklist counts it as not passed, and real money for C would need an explicit owner decision
  - Owner step: the repo secrets `FINNHUB_API_KEY`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` ([runbook](runbooks/paper-trading.md#owner-steps)). Until they exist every verdict is `failed` and C makes no trades
- Leaderboard, go-live checklist and Month by month landed with P4 (SPY is the champion); C appears in every roster view, and Positions shows its "Vetoed tonight" list
- **Done when:** A and C each have an independent paper portfolio; B failed P6a and is closed

## v0.1.0 release · pending the 5-night check
Paper-only (owner option (b), 2026-10-04): P0, P1, P2 and P5 done; P4 code landed and running on paper.
Release when P4's "Done when" holds: ≥ 5 consecutive paper sessions, `paper_check --require-sessions 5`
green on Neon. Then the README, then `gh release create v0.1.0`
([release checklist](runbooks/paper-trading.md#release-checklist-v010)). P6 may trail into v0.2.0.
`paper_check --require-sessions 5` counts every roster strategy, so once Strategy C is on the roster
the check also waits for C's 5th paper session.
The 3-month forward clock of design §1 starts on the first live paper day, but it unlocks nothing
by itself: no roster strategy has passed a backtest gate.

## Later (v0.2+)
- Real-trade journal: log actual Gotrade fills against Seer picks, real vs paper slippage
- Notifications (e.g. Telegram) for picks and day-5 exits
- Parameter/strategy versioning so changes reset the forward clock honestly

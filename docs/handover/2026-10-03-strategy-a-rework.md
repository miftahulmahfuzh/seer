# Handover — Strategy A rework under walk-forward validation (roadmap P3b)

Written 2026-10-03, after P3 landed on `main` @ `2e6994f` with a **failed gate**. Pass this file
straight to `/analyze` in a fresh session, and read all of it first. Like the P3 handover, it
separates decisions that are **already made**, facts that were **verified**, and questions the
analysis still has to settle.

## 1. Where we are (one paragraph)

Seer proposes up to 4 US stocks each night, each with a Limit / TP / SL bracket the owner types
into Gotrade. Real money goes in only after a strategy passes the fixed go-live checklist (design
§1). P3 implemented Strategy A (Connors-style RSI(2) mean reversion, design §4) and backtested it
over 10 years through the P2 simulator. **It failed honestly.** Out of sample (2022-01-03 →
2026-10-02) it returned **−15.0%** against **+71.9%** for total-return SPY, with profit factor
0.92 and max drawdown 33.3%. ROADMAP P3 says: *rework before P4; P4 must not start.* This
handover is that rework, done once and under a protocol that cannot fool us.

Read before planning:
- `docs/backtests/2026-10-02-strategy-a.md`: the P3 report. Its numbers are the baseline.
- `docs/handover/2026-10-03-strategy-a-backtest.md`: the P3 handover. Its §3 rules still hold
  unless §3 below changes them.
- `docs/plans/2026-10-03-seer-design.md`: **§1 go-live checklist and §5 trade rules are law.**
  §4's Strategy A rules are "starting rules", so the rework may change them.
- `engine/package_readme.md`: the `strategies`, `backtest` and `sim` sections, the `backtest`
  command, and `## Performance`.
- `docs/ROADMAP.md`: P3's verdict line.

## 2. What the P3 report tells us (verified, 2026-10-02 data)

- **It loses in-sample too.** In-sample (2015-10-19 → 2021-12-31) Strategy A made +43.6% while
  total-return SPY made +145.4%. **None of the 81 grid runs qualified** (max DD ≤ 15% and PF ≥
  1.3); the best profit factor was 1.24. The design values were kept as the fallback. The problem
  is the strategy, not overfitting.
- **Thin edge per trade.** Win rate is 54–60% and average holding is about 3.3 days. Exits split
  roughly TP 49%, SL 20%, time stop 25%, gap at the open 6%. The 0.2% round-trip cost is a large
  share of a 1×ATR take-profit.
- **Always fully invested, so ranking matters.** `no_slot` rejected 32,169 picks in-sample and
  26,510 out of sample. There are far more candidates than slots, so *which* candidates get the 4
  slots (today: the deepest RSI(2)) drives the result.
- **Small account.** 20,000,000 IDR is about $1,468 (in-sample start) or $1,402 (OOS start), so a
  slot is about $350–370. Many positions are 1–3 shares. `lt_one_share` rejected 103 picks
  in-sample and 642 OOS. Whole shares are a Gotrade limit-order rule (design §2) and cannot change.
- **No market regime filter.** Strategy A keeps buying dips through 2022's bear market. Its OOS max
  drawdown (33.3%) was deeper than SPY's (22.7%).
- **Survivorship.** 115 index members in the window have no bars at all. The results are, if
  anything, *better* than reality.
- **Fast infrastructure.** Load is 0.7 s from the cache (about 25 s cold from Neon),
  `STRATEGY_A.prepare` takes 2.8 s, and one 6-year run takes about 0.5 s.

## 3. Decisions

### Law — do not reopen

| Topic | Rule |
|---|---|
| Go-live checklist | Design §1, all 5 items, unchanged. The gate thresholds stay: beat total-return SPY, PF ≥ 1.3, max DD ≤ 15% |
| Trade rules | Design §5 as implemented in `seer_engine.sim` (4 slots, equity ÷ 4, whole shares, strict-low fill, SL first, 5-day time stop, 0.1% per side). **No simulator change** |
| Brackets | Every pick is a fixed Limit/TP/SL set at order time (Gotrade bracket). No trailing exits and no exit rules that need a nightly price change |
| No look-ahead | Picks for session S use bars through `prev_session(S)` only, from the point-in-time universe |
| P4 identity | Whatever the rework adds must keep P3's contract: `picks_prepared(prepare(H), …) == picks(upto(d), …)`, with indicators bit-identical over a fixed trailing window |
| P3 record | `strategies/a.py`, `STRATEGY_A_PARAMS`, `test_strategy_a_frozen.py` and `docs/backtests/2026-10-02-strategy-a.*` stay as they are. They are the honest record of v1 |
| DB | Read-only on Neon. Nothing writes `strategies.params` (P4 owns that) |

### Decided in this handover

These are recommendations; each can be overturned with a one-line change before planning. They
are fixed **now, before anyone sees a new result**, which is the point.

| Topic | Decision | Why |
|---|---|---|
| The OOS window is burned | 2022-01-03 → 2026-10-02 has been looked at once. Any variant judged on it again is not out-of-sample any more. The rework therefore validates with an **anchored walk-forward**, and the report shows the old split only as "seen before" | Re-using a window you have seen is how backtests lie. Walk-forward also serves P6, since design §4 already asks for one for Strategy B |
| Walk-forward folds | Anchored, yearly. For each trade year Y in 2018…2026, tune on `IS_START` (2015-10-19) → the last session of Y−1, then trade Y (the first session of Y → the last session of Y, or the data end). The traded segments form **one continuous portfolio** from 2018-01-02 to the data end. Parameters switch at each year boundary, and open orders keep the brackets they were placed with | Tests the *procedure*, so no single split decides. The first fold still has about 2.2 years to tune on |
| Pre-registered variants | Exactly these four, defined below. No others are added after results are seen | A small fixed set limits data snooping. V1 and V2 are standard Connors-literature filters, not ideas mined from v1's trade log |
| V0 `control` | Strategy A v1 rules exactly | Shows what walk-forward does to v1. Expected to fail |
| V1 `regime` | V0, plus **no new picks on a `data_date` where SPY's close ≤ SPY's SMA(200)** | Connors' own market filter. It targets the 2022 failure mode, and it is a rule from the literature, not a parameter |
| V2 `regime_calm` | V1, but candidates are ranked by **ATR(14)/close ascending** (ties: RSI(2), then symbol) instead of deepest RSI(2) | Slots are oversubscribed, so the ranking picks the trades. The calmest dips gap through SL less often |
| V3 `regime_calm_floor` | V2, plus candidates must have a **close ≥ $10** | A sanity floor against penny-like moves that ATR brackets handle badly. It is fixed, not tuned |
| Search space | Each fold searches (variant × the P3 81-run grid) = **324 combinations** together. The fold's selection uses P3's rule unchanged: highest tuning-window total return among combinations with max DD ≤ 15% and PF ≥ 1.3; ties go to lower DD, then to the order variant → grid. **If none qualifies, the fold trades V0 with the design values** | Choosing the variant inside each fold means the walk-forward result also prices in the variant choice. Nothing is selected on traded data |
| Per-variant transparency | The report also shows each variant's own walk-forward curve (variant fixed, grid tuned per fold), every fold's selection, and every fold's tuning-window table | Shows how fragile the result is. Report every run, not just the winner |
| Gate (P3b) | **A2 passes only if the walk-forward curve (2018-01-02 → data end) beats total-return SPY over the same span, with PF ≥ 1.3 and max DD ≤ 15%**, measured with P3's `metrics` (web parity) | Same thresholds as design §1, applied to evidence that was never tuned on |
| Deployed parameters | If the gate passes, the frozen A2 = the **last fold's** selection (tuned through 2025-12-31). Freeze it in code with a comment naming the report, as P3 did | Walk-forward validates the procedure; deploying its latest output is the standard practice |
| One round only | This rework runs **once**. If A2 fails the gate, Strategy A is not reworked again on this data. The report and ROADMAP say so, and P4 stays blocked | Rework round after rework round on the same 11 years is the overfitting this project exists to avoid |
| Code shape | A new pure strategy module (for example `strategies/a2.py` with `A2Params` and `STRATEGY_A2`, id `"A2"`) that reuses `strategies/indicators.py` and `a.py`'s helpers where it can. `a.py` is not changed. V1 reads SPY from the same `history` mapping (SPY is already in `Market.history`; P4 will need its last 200 bars too) | Keeps v1's frozen record intact and P4's call shape unchanged |
| Walk-forward code | A new pure module (for example `backtest/walkforward.py`) that defines the folds, runs the per-fold grid, and drives **one continuous portfolio whose params change by date**. Settle whether that means extending `run_backtest` to accept a params schedule (a `date → params` function) or a separate runner that reuses its loop. Purity and determinism rules as in P3 | P6 Strategy B will reuse it |
| Command | A new command (for example `backtest-wf`), or a `--walk-forward` mode of `backtest`, read-only, writing `docs/backtests/<data end>-strategy-a2-walkforward.md` + `-equity.csv` + `-equity.svg`. The `backtest` command's v1 output must stay byte-identical | Reproducible, and the v1 report doesn't move |
| Diagnostics | The report adds, for the walk-forward curve and for each variant: P/L by exit reason, P/L by year, the share of trades with < 3 shares, and the cost drag (Σ costs ÷ Σ gross P/L). These **explain** the result. They never feed selection | Helps the owner understand *why*, without a second tuning loop |
| Runtime | About 9 folds × 324 runs on growing windows. At about 0.08 s per traded year that is roughly 20–30 min. If the measured time is over 60 min, parallelize across processes and gather results in a fixed order. **Never shrink the variants or the grid after results** | The P3 rule, unchanged |

## 4. Verified facts (2026-10-03) — trust these

- **P3 is on `main` @ `2e6994f`** (pushed). The orchestration-prune commit `fd889b4` is on top.
  The P3 modules are `strategies/{base,indicators,a}.py` and
  `backtest/{market,runner,benchmark,metrics,tuning,report,io}.py`, plus `commands/backtest.py`.
  - `run_backtest(market, strategy, params, start, end, *, prepared=None, initial_idr=…)` returns
    a `RunResult`.
  - `tuning.select`/`gate`/`grid()`, `metrics.run_metrics`/`curve_metrics`/`checklist` (web
    parity) and `benchmark.spy_curves` (price-only and total-return, dividends vendored in
    `engine/data/spy_dividends.csv`) are all in place.
- **The P3 decisions all carry over**: the 200-bar indicator window, the float/Decimal boundary,
  "gone" = `last_bar_date < S` → `close_unpriced`, the curve start snapshot at
  `prev_session(start)`, starting FX = the latest `fx_rates` row on or before the start, end-of-
  window marking with no liquidation, and selection tie-breaks.
- **Tests:** the full engine suite is green with 0 skipped (`PG_TEST_URL` set). `test_strategy_purity.py`
  globs every `strategies/*.py` and every `backtest/*.py` except `io.py`, so new modules are covered
  automatically.
- **Data:** `bars` 1,817,429 rows, 663 symbols, 2015-01-02 → 2026-10-02. The nightly job may add
  sessions from Mon 2026-10-05 23:00 UTC, so record the data end the run actually used.
- **Cache:** `engine/.cache/bars-<max date>-<rows>.pkl` (gitignored, about 90 MB).

## 5. Environment

- WSL2 Ubuntu, **zsh** (`${(P)name}`, not `${!name}`). Python 3.11 via pyenv, no `uv`.
- **A worktree has no `engine/.venv`, and main's venv is an editable install of `/home/miftah/seer`,
  so it tests the wrong tree.** In a worktree, run
  `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'` first.
- Tests: `docker start seer-pg`, then
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`.
- **Real run from a worktree:** `SEER_ENV_FILE=/home/miftah/seer/.env.local`, because
  `config.REPO_ROOT` resolves to the worktree. Never `source` `.env.local`, since `DATABASE_URL`
  has an unquoted `&`. Raw `psql` to Neon hangs from WSL (IPv6); use the engine.
- The repo is public on purpose, and backtest reports may be public, including losing ones.

## 6. Acceptance criteria

1. **Variants:** tests for each of V1–V3's added rule on synthetic data. Regime off when SPY's
   close ≤ SPY's SMA(200), including the boundary case of equality. The ATR% ranking with its tie
   order. The $10 floor at exactly 10.0000. V0 picks are `==` Strategy A v1's picks for the same
   params.
2. **P4 identity and no look-ahead** hold for every variant (the same tests as P3, extended),
   including SPY's own bars: changing any SPY bar dated ≥ S leaves S's picks unchanged.
3. **Walk-forward:** tests on synthetic data that the folds are exactly as defined. Each fold's
   selection sees only its tuning window: changing any bar inside a traded year leaves that fold's
   selection unchanged. The traded segments chain into one portfolio, and a pending or open order
   at a year boundary keeps its bracket. The none-qualifies fallback is used.
4. **Determinism:** the same inputs give `==` results and byte-identical report files. Results
   gathered from a parallel run come back in a fixed order.
5. **Purity:** the new modules pass the globbing purity test.
6. **Real run:** one walk-forward run on Neon, report committed under `docs/backtests/`, containing:
   - every fold's selection and tuning table;
   - the per-variant curves;
   - the walk-forward curve vs both SPY curves;
   - the diagnostics;
   - the old OOS window labelled "seen before";
   - the survivorship note;
   - the P3b gate verdict in one sentence.
7. **Freeze or stop:**
   - If the gate passes, the frozen A2 params are in code with a comment naming the report, and a
     test ties code to report (like `test_strategy_a_frozen.py`).
   - If it fails, ROADMAP says that Strategy A's one rework failed and P4 stays blocked. The
     report lists what was tried.
8. The `backtest` command's v1 report is byte-identical to the committed one when re-run on the
   same data. `engine/package_readme.md` documents the variants, walk-forward and the new command.
   The full suite is green with 0 skipped, and CI stays green.

## 7. Open questions for the analysis to settle (recommend, don't ask open-ended)

- **Params schedule vs separate runner.** Can `run_backtest` take a `date → params` schedule
  without changing v1's results (prove it with the v1 byte-identity check), or does walk-forward
  need its own loop? Prefer extending it, with a default that keeps today's behaviour.
- **Fold tuning cost.** Each fold's 324 runs re-simulate its whole growing tuning window. Confirm
  `prepare` runs once per variant over all history (it is param-independent and look-ahead-safe by
  construction), and measure before deciding to parallelize.
- **Variant-in-params or variant-as-strategy.** One `A2Params(variant=…, rsi_max, limit_atr,
  tp_atr, sl_atr, …)` with a closed set of variant names, or four strategy objects? Prefer one
  params type, because the selection then works over a single combination list.
- **SPY in V1's `history`.** P3's `features_at` ignores non-members, and SPY is never a member.
  Settle how the strategy reads SPY's SMA(200) for the regime check, and confirm SPY can never
  become a pick.
- **The walk-forward start of the SPY benchmark.** Use the same start snapshot convention as P3
  (starting cash at `prev_session(2018-01-02)`, fresh 20,000,000 IDR at that date's FX).
- **Report layout.** One file with every fold table could be long (9 × 324 rows). Recommended: the
  main report holds per-fold top-10 tables plus the selection, and a companion CSV
  (`-grid.csv`) holds every run.

## 8. If the gate fails again — what the owner decides next (not part of P3b)

Not for this rework to decide, but the report should end by naming the options plainly:
- (a) Go to P6's Strategy B (ML ranker, walk-forward validated with the same new machinery).
- (b) Accept that SPY buy-and-hold is the honest champion for now. Seer can still paper-trade
  research strategies, but recommends no real-money picks.
- (c) Revisit a design-§5 trade rule (for example the 5-day time stop or the 4 slots). That is a
  design change, so it needs the owner's explicit decision and a new handover; it is never done
  inside a rework.

# Handover — Seer Strategy A + 10-year backtest (roadmap P3)

Written 2026-10-03, after P2 (fill simulator) landed on `main` @ `2863861`. This file is meant to
be passed straight to `/analyze` in a fresh session. Read all of it first. It separates decisions
that are **already made**, facts that were **verified**, and the questions the analysis still
has to settle.

## 1. What Seer is (one paragraph)

Seer is a personal web app. Every night it proposes up to 4 US stocks (slots S-E-E-R) to buy in
the next US session. Each pick comes with a **Limit Buy, Take Profit, Stop Loss and whole-share
count**, which the owner types into a Gotrade bracket order. Several strategies paper-trade side
by side on 20,000,000 IDR each. Real money only goes in once the champion strategy passes a fixed
go-live checklist. The owner is new to trading. What matters is **measured profit against buying
and holding SPY**, not how elegant the method is.

Read before planning:
- `docs/plans/2026-10-03-seer-design.md`: **§1 go-live checklist, §4 Strategy A rules and §5
  trade rules are law.**
- `docs/ROADMAP.md`: P0–P6. **This handover covers P3 only.**
- `engine/package_readme.md` → `### sim (fill simulator, P2)`, `### Simulator: P3 backtest loop`
  and `## Performance`. This is the API P3 drives. **Do not change simulator behavior**; see §3.
- `web/lib/metrics.ts`: how the web computes total return, win rate, profit factor and max
  drawdown. The backtest report must use the same definitions.
- `docs/runbooks/data-pipeline.md` ("First run"): what is in Neon, and the 133 symbols that
  could not be fetched.
- `db/migrations/001_init.sql`, `002_engine.sql`: `bars`, `universe`, `fx_rates`, `strategies`.

## 2. Goal of this task (P3, Strategy A + backtest)

Implement Strategy A and a 10-year backtest that runs it through the **P2 simulator**, then give
an honest verdict on whether it beats SPY.

It must:
1. Compute Strategy A's signals (design §4) from split-adjusted daily bars, using only data
   available at the `data_date` close (no look-ahead), and turn them into ranked `sim.Pick`s.
   Put this behind a small strategy interface, because P4 calls the same code nightly and P6 adds
   strategies B and C next to it.
2. Run a backtest over the point-in-time universe (S&P 500 ∪ Nasdaq-100 members on each
   `data_date`) for every NYSE session in the window, using `sim.size_picks` → `sim.step` →
   `sim.close_unpriced` exactly as the readme's "P3 backtest loop" shows.
3. Build the SPY buy-and-hold benchmark curve over the same window, net of the same 0.1% costs.
4. Tune parameters on the early years only, validate on the later years without tuning, then
   **freeze** the parameters in code.
5. Produce a backtest report: equity curve vs SPY, total return, CAGR, win rate, profit factor,
   max drawdown, trade count, exit-reason breakdown, and the go-live criteria from design §1
   that a backtest can evaluate. Report the in-sample and out-of-sample windows separately.

**Done when:**
- Strategy A and the backtest runner are implemented and tested on synthetic data (indicators
  against hand-computed values, no look-ahead, universe point-in-time, delisting handled).
- One real 10-year run on the Neon data is done, and its report is committed in the repo.
- The frozen parameters are in code, and the report states the **gate verdict**.
- The full engine suite is green with 0 skipped, CI stays green, and the API is documented in
  `engine/package_readme.md`.

**The gate (ROADMAP P3):** if Strategy A cannot beat SPY in the backtest, **stop and report it**.
Do not start P4, and do not tune on the validation window to rescue it. A losing verdict, honestly
measured, is a successful P3. Tuning until the number looks good is the failure mode this project
exists to avoid.

**Out of scope, don't build:** nightly wiring, writing `orders`/`equity_snapshots`/`strategies.params`
to Neon (P4), LLM explanations (P4), strategies B and C (P6), any web change, any change to
simulator rules.

## 3. Decisions already made — do not reopen

From the design doc (law):

| Topic | Rule |
|---|---|
| Strategy A setup | close > SMA200, RSI(2) < 10, average daily dollar volume > $20M |
| Limit / TP / SL | Limit = prior close − 0.5 × ATR(14); TP = limit + 1.0 × ATR(14); SL = limit − 1.5 × ATR(14) |
| Ranking | Deepest RSI(2) first; fill free slots |
| Universe | S&P 500 ∪ Nasdaq-100, point-in-time membership for backtests |
| Trade rules | Design §5 as implemented in `seer_engine.sim`. All sizing, fills, exits and costs go through the simulator; P3 never re-implements any of them |
| Benchmark | SPY buy-and-hold over the same period, net of costs |
| Tuning | Tune on early years, validate on later years, no tuning on the validation window, then freeze |
| Gate | If A cannot beat SPY in backtest, rework before P4 |
| Go-live #5 | A strategy must pass a 10-year backtest under identical rules |

Settled by P2 (see `engine/package_readme.md` → `### sim`):

| Topic | Rule |
|---|---|
| One code path | The backtest drives `seer_engine.sim` (`new_portfolio`, `size_picks`, `step`, `close_unpriced`). The sim is pure: no DB, network, clock or randomness |
| Picks | `sim.Pick(symbol, last_price, limit_price, tp_price, sl_price)`, all `Decimal` at 4 dp, `sl < limit < tp`. Rank order is the order of the list |
| Splits | Backfilled history is already split-adjusted backwards, so the backtest never calls `apply_split` |
| Delisting | When a held symbol's bars end for good, the caller calls `close_unpriced` (forced exit at the last close, reason `time`) |
| Starting cash | `initial_cash_usd(20_000_000, usd_idr on the start date)` from `fx_rates` |
| Performance | The simulator does 2,950 sessions × 4 slots in about 0.2 s. A backtest's cost is loading bars and computing signals |

Decided in this handover. These are recommendations for an owner who is new to trading; each one
can be overturned with a one-line change before planning:

| Topic | Decision | Why |
|---|---|---|
| Indicator definitions | SMA200 is the simple mean of the last 200 closes. RSI(2) and ATR(14) use **Wilder smoothing** (the Connors RSI(2) convention). True range uses the previous close. Dollar volume is the 20-session mean of `close × volume` | These are the standard definitions behind the design's rules. Each is stated so the tests can pin it |
| Signal timing | Picks for session S use bars through `prev_session(S)` (the `data_date`) only. `last_price` = that close | This is exactly what the nightly job will see. A test must prove that a bar dated S cannot change S's picks |
| Eligibility | A symbol must be a member on `data_date`, have a bar on `data_date`, and have at least 200 sessions of history | SMA200 is undefined before that. No partial windows |
| Prices | Limit/TP/SL are computed in `Decimal` and quantized to 4 dp (`sim.q`). A pick whose quantized SL ≥ limit, or limit ≤ 0, is dropped | The sim rejects them anyway; dropping them in the strategy keeps the reason visible |
| Ties | Equal RSI(2) → break the tie by symbol, ascending | Determinism |
| Window | Bars start 2015-01-02, so SMA200 is ready around 2015-10-19. **In-sample (tuning): 2015-10-19 → 2021-12-31. Out-of-sample (validation): 2022-01-03 → the last bar (2026-10-02 today).** One continuous portfolio is reported over the full window, plus separately started portfolios for each window | Gives ~6 years to tune and ~4.75 years to validate, and the validation window includes the 2022 bear market |
| Benchmark details | Buy SPY at the **open** of the first session with as many whole shares as the starting cash allows after 0.1% cost; hold; mark at each close; never sell (or sell at the last close with cost when reporting the final number). Cash remainder sits idle | Same costs and whole-share rule as the strategy |
| SPY dividends | Report **two** SPY curves: price-only (from `bars`) and total-return (dividends reinvested on the ex-date at that close). **The gate uses total-return SPY** | `bars` are split-adjusted only. Price-only SPY drops about 1.3–1.8%/yr of dividends, roughly 15–20% over 10 years, which would hand Strategy A a fake win. Strategy A barely holds anything across ex-dates. Being conservative here is the honest choice |
| Survivorship | 133 ever-members have no bars (delisted or acquired; Yahoo no longer serves them, e.g. SIVB, FRC, CHK, ATVI, CELG). The backtest can only trade symbols with bars. The report must state this bias in plain words and give the count of (member, session) pairs with no bars per year | A dip-buying strategy is exactly the kind that the missing collapses (SIVB, FRC) would have hurt. This cannot be fixed on free data, but it must not be hidden |
| Tuning | A **small** grid, chosen before seeing results, around the design values: RSI threshold {5, 10, 15}; limit offset {0.25, 0.5, 0.75} × ATR; TP {0.75, 1.0, 1.5} × ATR; SL {1.0, 1.5, 2.0} × ATR (81 runs). Select on in-sample results only, by the highest in-sample return **among runs with max drawdown ≤ 15% and profit factor ≥ 1.3**; if none qualifies, keep the design values. Report every grid run, not just the winner. Then run the winner once on out-of-sample | A small grid limits overfitting. Reporting all runs shows how fragile the result is. Keeping the design values as the fallback means "nothing worked" is a visible outcome |
| Gate verdict | A passes the gate only if, **on out-of-sample**, total return > total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%. In-sample results are shown but never decide the verdict | Matches go-live criteria 2–5. In-sample performance after tuning is not evidence |
| Metrics | Same definitions as `web/lib/metrics.ts`: a loss is `pnl ≤ 0`; profit factor = gross win / gross loss (∞ when no loss); max drawdown on per-session snapshot equity; total return = last / first − 1. Add CAGR, trade count, average `days_held` and the exit-reason breakdown | The web leaderboard must show the same number later. Add a parity test with the same inputs as `web/lib/metrics.test.ts` |
| DB use | The backtest **reads** Neon (bars, universe, fx_rates) and writes nothing to it | Backtest results are not paper trades. P4 owns DB writes |
| Purity | Indicator and strategy code is pure (takes bars/arrays, returns picks), like the sim. DB loading lives in a separate module. Extend the purity test to the strategy module | One code path for P4, and fast offline tests |
| Frozen parameters | A frozen dataclass in code (for example `STRATEGY_A_PARAMS`), with a comment pointing at the report that froze it | P4 writes it to `strategies.params`; P3 doesn't touch the DB |

## 4. Verified facts (2026-10-03) — trust these

- **P2 is on `main` @ `2863861`** (pushed; CI green on that commit). `seer_engine.sim` exports
  `new_portfolio, initial_cash_usd, size_picks, step, close_unpriced, apply_split, Pick, Order,
  Portfolio, Event, Snapshot, StepResult, …`. `seer_engine.prices` holds the pure `Bar`,
  `PRICE_QUANTUM` and `to_decimal`, and `seer_engine.bars` re-exports them.
- **Tests:** 374 engine tests pass, with 0 skipped (`PG_TEST_URL` set). `engine/tests/simkit.py` has
  synthetic bar and order builders (`D`, `P`, `bar`, `day`, `pending`, `opened`, `portfolio`).
- **Data on Neon** (runbook "First run"):
  - `bars`: 1,817,429 rows across 663 symbols, 2015-01-02 → 2026-10-02, 177 MB, split-adjusted
    and not dividend-adjusted.
  - SPY covers all 2,955 NYSE sessions in that range with no gaps.
  - `universe`: 1,544 intervals; 795 symbols were members at some point since 2015; current
    union = 518. Intervals are `[start_date, end_date)`.
  - `fx_rates`: 3,009 rows of USD/IDR.
  - 133 symbols are logged `empty` in `backfill_log`, and none of them is a current member.
- **Engine APIs:**
  - `universe.members_on(conn, d)` runs one query per date. For 2,950 sessions, load the
    `universe` table once and evaluate it in memory instead.
  - `dates.sessions(start, end)`, `next_session`, `prev_session`, `is_session` (NYSE).
  - Commands are discovered from `seer_engine/commands/*.py`, so a new `backtest` command never
    edits `cli.py`.
  - `db.connect()` + `contextlib.closing`. Never `with psycopg.connect(...)`, because it commits
    on exit.
- **Environment:** pandas 3.0.6 and numpy 2.4.6 are installed. **pyarrow is not** (no Parquet
  without adding a dependency). matplotlib is not installed.
- **Repo secrets are now set** (`DATABASE_URL_UNPOOLED`, `MASSIVE_API_KEY`, 2026-10-03 06:41
  UTC), so the nightly workflow should succeed from Mon 2026-10-05 23:00 UTC.

## 5. Environment

- Local: WSL2 Ubuntu, **zsh** (use `${(P)name}`, not `${!name}`).
- Python 3.11 via pyenv, no `uv`. The main checkout's venv is at `engine/.venv`.
  **A worktree has no `engine/.venv`, and the main checkout's venv is an editable install of
  `/home/miftah/seer`, so it would test the wrong tree.** In a worktree, run
  `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'` first.
- Tests: `docker start seer-pg`, then
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`.
- `.env.local` at the repo root holds every key. Never `source` it, because `DATABASE_URL` has an
  unquoted `&`; the engine loads it with dotenv.
- Raw `psql` to Neon hangs from WSL (IPv6). Use the engine or Python instead.
- The real backtest run needs Neon (read-only). Loading all of `bars` is about 177 MB over the
  network.
- The repo is public on purpose. Ask the owner before `git push` or `gh secret set`.

## 6. Acceptance criteria

1. **Indicators:** SMA200, Wilder RSI(2), Wilder ATR(14) and 20-day dollar volume each have tests
   against hand-computed values on synthetic series, including the warm-up boundary (no value
   before enough history).
2. **No look-ahead:** a test where changing any bar dated on or after session S leaves S's picks
   unchanged.
3. **Strategy A picks:** tests for the setup filter (each condition on its own), the
   limit/TP/SL formulas to 4 dp, ranking by RSI(2) with the symbol tie-break, dropping invalid
   prices, and non-members being excluded on that `data_date`, including a symbol that joins or
   leaves the index mid-window.
4. **Runner:** a synthetic multi-symbol backtest (no DB) that goes through `size_picks` → `step`
   → `close_unpriced`, including a held symbol whose bars end (forced close) and a session with 0
   picks. Final equity and trade list are hand-checked.
5. **Benchmark:** tests for the SPY price-only and total-return curves on synthetic bars plus a
   dividend, including the whole-share purchase and costs.
6. **Metrics:** a parity test against the same inputs and expected values as `web/lib/metrics.test.ts`.
7. **Determinism:** the same inputs give an identical report (no clock reads in the core, sorted
   iteration).
8. **Purity:** the strategy and indicator modules import nothing from `psycopg`, `requests` or
   `yfinance` (extend `test_sim_purity.py` or add a sibling).
9. **Real run:** a `backtest` command (read-only on Neon, `--dry-run` irrelevant) produces the
   committed report: in-sample grid table, chosen parameters, out-of-sample result, full-window
   curve vs both SPY curves, survivorship note, and the gate verdict in one sentence.
10. `engine/package_readme.md` documents the strategy interface (for P4 and P6), the backtest
    command, and the report. The full engine suite is green with 0 skipped, and CI stays green.

## 7. Open questions for the analysis to settle (recommend, don't ask open-ended)

- **Strategy interface.** Recommended: a pure
  `picks(history, members, data_date, params) -> list[sim.Pick]`, where `history` is
  per-symbol bars up to and including `data_date`. Put it in `seer_engine/strategies/`
  (`base.py` with the protocol, `a.py` for Strategy A), so P4 calls the same function with the
  last 250 sessions it loads from Neon. Settle the exact `history` shape: pandas frames per symbol
  with precomputed indicator columns are fast in a backtest, but per-night recomputation must
  give identical numbers.
- **Float vs Decimal in signals.** Recommended: compute indicators in float64 (pandas/numpy) for
  speed, then convert limit/TP/SL to `Decimal` through `to_decimal` (repr-based, 4 dp) at the
  boundary. Settle whether float rounding can flip a strict comparison (e.g. RSI exactly 10.0)
  and document it.
- **Loading bars.** Recommended: load `bars` once per run with one streamed query (or `COPY TO
  STDOUT`) into a local cache file under a gitignored `engine/.cache/`, keyed by
  `max(date)` + row count, so grid runs don't re-download 177 MB. With no pyarrow, use pickle or
  `csv.gz`, or add pyarrow as a dev dependency. Settle which.
- **Where SPY dividends come from.** Recommended: fetch SPY's dividend history once with yfinance
  (`Ticker("SPY").dividends`), vendor it as `engine/data/spy_dividends.csv`, and add its source
  entry to `engine/data/SOURCES.md`. The run then needs no network beyond Neon. The alternative
  is a new `dividends` table, which is more machinery than one benchmark needs.
- **When is a held symbol "gone"?** Recommended: in the backtest, a symbol is gone at session S
  when it has no bar on S and no bar on any later session in the loaded data. Then call
  `close_unpriced` after S's step. Settle what happens on a halt of a few days (bars resume)
  versus a real delisting.
- **Report format and location.** Recommended: `docs/backtests/2026-10-XX-strategy-a.md` (tables
  and verdict) plus a CSV of the daily equity curves (strategy, SPY price-only, SPY total-return)
  next to it, and one chart as a self-contained SVG written without new dependencies. Settle
  whether the grid table goes in the same file.
- **Grid runtime.** 81 runs × ~2,950 sessions. Signals can be computed once per (RSI threshold)
  since only the price offsets change with the other parameters. Confirm the full grid runs in
  minutes, not hours, or shrink it before looking at any results.

## 8. Not part of P3, but pending (owner)

- **GPS → GAP alias** is still missing (Gap Inc. renamed), so `GPS` is logged `empty`. See the
  runbook's "Renames going forward".
- **P0** still lists "lint" as open; the repo has no lint script.
- The first scheduled nightly run is Mon 2026-10-05 23:00 UTC. It is worth checking the Actions
  log the morning after.

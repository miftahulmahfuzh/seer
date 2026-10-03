# Handover: Strategy B, ML cross-sectional ranker, walk-forward backtest (roadmap P6a)

Written 2026-10-03, after P3b landed on `main` @ `de71cbd` with a **failed** gate. Pass this file
straight to `/analyze` in a fresh session, and read all of it first. Like the P3 and P3b handovers,
it separates three things:
- decisions that are **already made**;
- facts that were **verified**;
- questions the analysis still has to settle.

## 1. Where we are, and why this is the next phase

Seer proposes up to 4 US stocks each night. Each pick comes with a Limit / TP / SL bracket that the
owner types into Gotrade. Real money goes in only after a strategy passes the fixed go-live
checklist (design §1).

**Strategy A is finished on this data.** v1 failed the P3 gate. Its one pre-registered rework, A2,
failed the P3b walk-forward gate as well: from 2018-01-02 to 2026-10-02 it returned **+9.1%**
against **+187.6%** for total-return SPY, with PF 1.02 and max DD 29.1%. ROADMAP P3b says Strategy
A is not reworked again, P4 stays blocked, and the owner picks one of three options:
- **(a)** Strategy B;
- **(b)** SPY as the honest champion;
- **(c)** a design-§5 change.

**This handover takes (a)**, for three reasons:
- **It is already the plan of record.** The roadmap has Strategy B in P6, design §4 lists it as "ML
  cross-sectional ranker, walk-forward backtest + forward paper", and P4 is blocked until some
  strategy passes. So B moves ahead of P4. It is research-only and read-only, and it touches no
  trade rule.
- **Most of the machinery exists.** P3b built the anchored yearly folds, the params schedule, the
  one-portfolio walk-forward runner, the diagnostics, the gate and the report layout. Design §4
  already called for this machinery for B.
- **It leaves (b) and (c) open.** If B fails, the same three options come back, minus (a).

**Overturning this choice costs one line.** Option (b) needs no engine work, only a ROADMAP and UI
decision. Option (c) needs a new design handover. Neither belongs in this file.

Read before planning:
- `docs/backtests/2026-10-02-strategy-a2-walkforward.md`: the P3b report. Its walk-forward curve and
  its diagnostics are the baseline B is compared against.
- `docs/handover/2026-10-03-strategy-a-rework.md`: the P3b handover. Its §3 "Law" table still holds
  unless §3 below changes it.
- `docs/plans/2026-10-03-seer-design.md`. **§1 (the go-live checklist) and §5 (trade rules) are
  law.** §4 names Strategy B.
- `engine/package_readme.md`: the `strategies`, `backtest` and `sim` sections, `backtest_wf`, and
  `## Performance`.
- `docs/ROADMAP.md`: the P3b verdict and P6.

## 2. What P3 and P3b tell us (verified, 2026-10-02 data)

**1. A's edge before costs was tiny, and costs ate almost all of it.**

| Walk-forward diagnostic | Value |
|---|---|
| Gross P/L | +$1,035 |
| Costs | $901 |
| Net P/L | +$134 over 1,329 trades in 8.75 years |
| Cost drag | **87%** |
| Trades with < 3 shares | 36.9% |

The "calm" ranking (V2/V3) made it worse, with cost drag above 360%. Any strategy that trades
about 150 times a year on $350 slots must clear 0.2% per round trip on every trade. **B must be
trained on a net-of-cost target and must be allowed to pass on a night.** Zero picks is valid
(design §5).

**2. Tuning found almost nothing.** In 7 of 9 folds, none of the 324 combinations qualified
(DD ≤ 15% and PF ≥ 1.3 on the tuning window), so those folds traded the fallback.

**3. Slots are heavily oversubscribed.** `no_slot` rejected 50,682 picks over the walk-forward, so
the ranking decides which trades happen. A ranker is aimed at exactly this.

**4. The bar is high.**
- Total-return SPY made +187.6% (CAGR 12.8%) over 2018 → 2026-10-02, with a 30.2% max drawdown of
  its own.
- The gate asks for more return than SPY *and* at most half its drawdown.
- That is the law (design §1) and it does not move. The report should say plainly how high it is.

**5. Survivorship is unchanged.** 115 index members in the window have no bars at all. A learned
model can absorb that bias more than a rule can, because the losers it never saw are exactly the
ones it would have needed to learn to avoid. The report must say so.

**6. Infrastructure speed.**
- Loading the market takes 0.7 s from the cache and about 25 s cold.
- `prepare` takes about 3 s.
- One walk-forward run (2018 → 2026-10-02) takes about 0.8 s.
- The whole `backtest_wf` command took 4:13.

## 3. Decisions

### Law: do not reopen

| Topic | Rule |
|---|---|
| Go-live checklist | Design §1, all 5 items, unchanged. The gate thresholds stay: beat total-return SPY, PF ≥ 1.3, max DD ≤ 15% |
| Trade rules | Design §5 as implemented in `seer_engine.sim`: 4 slots, equity ÷ 4, whole shares, strict-low fill, SL first, 5-day time stop, 0.1% per side. **No simulator change** |
| Brackets | Every pick is a fixed Limit/TP/SL set at order time. No trailing exits, and no exit rule that needs a nightly price change |
| No look-ahead | Picks for session S use bars through `prev_session(S)` only, from the point-in-time universe. **This also holds for training labels** (see "Label purge" below) |
| P4 identity | B keeps the strategy contract `picks_prepared(prepare(H), …) == picks(upto(d), …)`. Features are bit-identical over a fixed trailing window, and predictions are bit-identical given the same model |
| P3 and P3b records | `strategies/a.py`, `a2.py`, their frozen constants and tests, and `docs/backtests/2026-10-02-strategy-a*` stay as they are. `backtest_wf`'s A2 output stays byte-identical |
| DB | Read-only on Neon. Nothing writes `strategies.params` (P4 owns that) |
| One round only | B runs **once** on this data. If it fails, B is not reworked on this data either. The report and ROADMAP say so |

### Decided in this handover (pre-registered before any B result exists)

These are recommendations, and each can be overturned with a one-line change before planning. They
are fixed **now, before anyone sees a B result**, which is the point.

| Topic | Decision | Why |
|---|---|---|
| Folds | **Exactly P3b's folds.** Anchored and yearly, trading 2018 … 2026, tuning from `IS_START` (2015-10-19) through the last session of Y−1. One continuous portfolio from 2018-01-02 to the data end. Reuse `walkforward.folds` | The same span as A2's walk-forward, so B, A2 and SPY sit on one chart. Nothing about the folds is chosen after seeing A |
| Candidates | Each `data_date`, every point-in-time member with ≥ 200 bars through `data_date`, a bar dated `data_date`, and 20-day mean close×volume > $20M (A's liquidity floor). SPY is never a candidate | The same eligible set A saw, so the comparison is about ranking, not universe |
| Bracket | **A's design bracket, fixed:** limit = close − 0.5×ATR(14), TP = limit + 1.0×ATR(14), SL = limit − 1.5×ATR(14), in Decimal at 4 dp. Reuse `strategies.a._bracket` | B changes *which* trades happen, not how they exit. Tuning the bracket again is the grid that already found nothing |
| Label | For each candidate (symbol, `data_date`): the **net return per dollar committed** of that one bracket order, simulated alone under design §5. Fill only if low < limit, at min(open, limit). TP/SL are checked from the session after the fill, with SL first on a both-in-range bar. Gaps fill at the open. The time stop exits at the next open after trading day 5. Costs are 0.1% per side. **An unfilled order labels 0.** Per share, so the label does not depend on share count | The target is exactly what the portfolio earns from a pick, after costs. That attacks the 87% cost drag at its root |
| Label purge | A label is **resolved** on its exit session, or on its expiry session if unfilled. Fold Y trains only on labels resolved on or before `tune_end(Y)`. A row whose trade was still open at `tune_end` is excluded | Without the purge, fold Y would learn from up to 6 sessions of year Y |
| Features | Fixed, all computed from the symbol's last 200 bars ending at `data_date` under the indicators' bit-identity rule. The list: returns over 1/5/20/60/120 sessions; close ÷ SMA(50) − 1; close ÷ SMA(200) − 1; RSI(2); RSI(14); ATR(14) ÷ close; 20-day stdev of daily returns; log 20-day mean dollar volume; 5-day ÷ 20-day mean volume; today's gap (open ÷ previous close − 1); range position (close − low) ÷ (high − low). Plus SPY's 5- and 20-session returns and SPY close ÷ SMA(200) − 1, which are the same for every candidate on a date. Every per-symbol feature is turned into a **cross-sectional rank in [0, 1]** among that date's candidates, with ties averaged. The SPY features stay raw | Generic, standard short-horizon features, chosen without reading A's trade log. Ranks make the model indifferent to scale and to the market's level |
| Model (gated) | **B = gradient-boosted regression trees** with fixed hyperparameters: scikit-learn `HistGradientBoostingRegressor(loss="squared_error", learning_rate=0.05, max_iter=300, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0, early_stopping=False, random_state=0)`. **No hyperparameter search.** Retrained once per fold on that fold's purged training rows | No search means no selection on noisy tuning metrics, which was P3b's failure mode. Trees capture interactions a rule cannot |
| Model (information only) | **B-linear = ridge regression** (alpha = 1.0, numpy closed form) on the same features and labels, run through the same walk-forward. It is reported next to B, **never gated, and never promotable on this data** | Shows whether any edge comes from non-linearity or from the features alone. Fixed now so it cannot become a second chance |
| Picks | Rank candidates by predicted label, descending (ties: symbol ascending). **Keep only predictions > 0.0.** Return every survivor with A's bracket; the simulator fills the free slots in order | A positive predicted net return is the only threshold with no free parameter. It lets B sit out nights instead of paying 0.2% for nothing |
| Gate (P6a) | **B passes only if its walk-forward curve (2018-01-02 → data end) beats total-return SPY over the same span, with PF ≥ 1.3 and max DD ≤ 15%**, measured with the existing `metrics` (web parity) | Same thresholds as design §1 and P3b |
| Deployed model | If the gate passes, the frozen B = **the last fold's model** (trained on labels resolved through 2025-12-31). Freeze it as a committed artifact plus a code constant naming the report, the training cut-off and the artifact's SHA-256. Add a test that ties code, artifact and report together, as `test_strategy_a_frozen.py` does | Walk-forward validates the procedure; deploying its latest output is standard practice. P4 needs a fixed model to predict with |
| Code shape | A new pure strategy module, for example `strategies/b.py` with `BParams(model=…)` and `STRATEGY_B` (id `"B"`). Feature and label code is pure numpy. Model fitting and prediction live behind a small pure interface (`fit(X, y) -> model` and `predict(model, X) -> float64`). `a.py` and `a2.py` are not changed | Keeps the protocol and P4's call shape unchanged. The params schedule already accepts any params object, so a per-fold model can be `params` |
| Walk-forward code | Generalize `backtest/walkforward.py` where it is A2-specific (`combinations`, `select_fold`'s A2 fallback), or add a B driver that reuses `folds`, `schedule`, `walk_forward`'s runner path, `diagnostics`, `window_metrics` and the gate. `backtest_wf`'s A2 output must stay byte-identical (test it). There is no per-fold selection step for B; each fold just trains | P3b's machinery, reused rather than forked |
| Command | A new read-only command, for example `backtest_b`. It writes `docs/backtests/<data end>-strategy-b-walkforward.md` + `-equity.csv` + `-equity.svg`, plus whatever per-fold model summaries the report needs. **A2's walk-forward curve appears on the chart and in the tables as information**, computed by re-running `backtest_wf`'s pipeline or by reading its committed CSV (analysis decides) | One page shows B, B-linear, A2 and both SPY curves over the same span |
| Report contents | Per fold: training rows, label mean, the model's in-fold fit (information), and the top features by permutation importance or the trees' split gain (analysis picks one and fixes it). The walk-forward vs both SPY curves. Year by year. P3b's diagnostics: P/L by exit reason and by year, < 3-share share, and cost drag. Also **the share of nights B passed** and **mean predicted vs realized label by prediction decile**, a calibration table that explains and never selects. Plus "seen before" (2022-01-03 →), the survivorship note (with §2.5's extra caveat for learned models), the go-live checklist, the one-sentence verdict, and on a fail the owner's next options | Explains *why* without a second tuning loop |
| Determinism | Same inputs give `==` results and byte-identical report files. HistGradientBoosting must give bit-identical predictions across two runs **and** across `OMP_NUM_THREADS=1` vs the default. If the analysis cannot make that hold, **the gated model becomes B-linear** and the tree model drops to information only. This switch is pre-registered here, so it is not a post-result choice | Byte-identical reports are law since P3 |
| Dependency | `scikit-learn` is added to `engine/pyproject.toml` with a pinned minor version. CI installs it | The one new dependency. A pinned version keeps a frozen model loadable |
| Runtime | Measure it. Label generation over about 1.3M candidate rows must be vectorized numpy, not one `sim.step` per row (§7). A test proves the vectorized labeler agrees with `sim` on a sample. Nine fits of about 1M × 18 should take minutes. Parallelize only if the whole command exceeds 60 min, gathering in a fixed order | The P3 rule, unchanged |

## 4. Verified facts (2026-10-03): trust these

- **P3b is on `main` @ `de71cbd`, pushed, and CI is green** (run 37118151067). The orchestration
  prune commit `5df303a` sits on top.
- **P3b modules:**
  - `strategies/a2.py`;
  - `backtest/{walkforward,wf_report}.py`;
  - additive changes to `backtest/{runner,metrics,tuning,io}.py`;
  - `commands/backtest_wf.py`.
- **Public pieces B can reuse:**
  - `runner.ParamsSchedule` (`params.at(S)`, keyed by the traded session);
  - `metrics.metrics_through`;
  - `walkforward.folds` / `schedule` / `walk_forward` / `diagnostics` / `window_metrics` /
    `curve_window_metrics` / `gate_p3b`;
  - `tuning.select(rows, *, fallback=)`.
- **Parts of `walkforward.py` that are A2-specific:** `combinations()` (324 `A2Params`),
  `select_fold`'s fallbacks and `_variant`. `gate_p3b`'s sentence names "Strategy A2" and "P3b", so
  B needs its own sentence.
- **Indicators.** `strategies/indicators.py` has SMA, Wilder RSI, Wilder ATR and mean dollar volume,
  each under the bit-identity rule (no `sum`/`mean`/`cumsum` along time, an explicit column loop).
  New window functions for B (stdev of returns, ratios) must follow the same rule. Its tests show
  how.
- **Tests:** the full engine suite is green with 0 skipped (`PG_TEST_URL` set).
  `test_strategy_purity.py` globs every `strategies/*.py` and every `backtest/*.py` except `io.py`,
  so new modules are covered automatically. Check that importing scikit-learn from a pure module
  does not pull in a forbidden module (psycopg, requests, yfinance).
- **Data:** `bars` has 1,817,429 rows, 663 symbols, 2015-01-02 → 2026-10-02. The nightly job may
  add sessions from Mon 2026-10-05 23:00 UTC, so record the data end the run actually used.
- **Cache:** `engine/.cache/bars-<max date>-<rows>.pkl` is gitignored, about 90 MB, and per
  checkout. A worktree starts cold.

## 5. Environment

- WSL2 Ubuntu, **zsh** (use `${(P)name}`, not `${!name}`). Python 3.11 via pyenv, no `uv`.
- **A worktree has no `engine/.venv`, and main's venv is an editable install of
  `/home/miftah/seer`, so it tests the wrong tree.** In a worktree, run
  `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'` first, and again
  after scikit-learn is added.
- Tests: `docker start seer-pg`, then
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`.
- **Real run from a worktree:** set `SEER_ENV_FILE=/home/miftah/seer/.env.local`, because
  `config.REPO_ROOT` resolves to the worktree. Never `source` `.env.local`: its `DATABASE_URL` has
  an unquoted `&`. Raw `psql` to Neon hangs from WSL (IPv6), so use the engine.
- The repo is public on purpose, and backtest reports may be public, including losing ones.

## 6. Acceptance criteria

1. **Labels:**
   - tests on synthetic bars for each label path: no fill (0), fill at the limit, fill at the open
     when open < limit, TP, SL, both in range (SL first), gap through TP or SL at the open, and
     the day-5 time stop, all net of 0.1% per side;
   - the vectorized labeler agrees with a one-order run of `seer_engine.sim` on a sample: same
     exit reason and same exit date, with the return equal within float tolerance;
   - the label purge: changing any bar dated after `tune_end(Y)` leaves fold Y's training set
     unchanged.
2. **Features:**
   - each feature is hand-computed on a synthetic series;
   - bit-identity between the rolling (`prepare`) and single-window (`picks`) paths;
   - ranks are computed among that date's candidates only, with ties averaged;
   - SPY features read SPY's bars through `data_date` only.
3. **P4 identity and no look-ahead** hold for B and B-linear: `picks_prepared(prepare(H)) ==
   picks(upto(d))` for a fixed model. Changing any bar dated ≥ S, SPY's included, leaves S's picks
   unchanged.
4. **Walk-forward:**
   - the folds are exactly P3b's;
   - each fold's model is trained only on purged labels resolved by its `tune_end`;
   - the traded segments chain into one portfolio, and brackets survive the year boundary;
   - **`backtest_wf`'s A2 report is byte-identical** to the committed one when re-run on the same
     data.
5. **Determinism:**
   - the same inputs give `==` results and byte-identical files;
   - the gated model's predictions are bit-identical across runs and across thread counts, or the
     pre-registered switch to B-linear took effect and the report says so.
6. **Purity:** the new modules pass the globbing purity test.
7. **Real run:** one walk-forward run on Neon, with the report committed under `docs/backtests/`.
   It contains:
   - every fold's training summary;
   - the B and B-linear curves vs A2 and both SPY curves;
   - the year-by-year table;
   - the diagnostics, including the passed-night share and the calibration table;
   - "seen before";
   - the survivorship note;
   - the P6a gate verdict in one sentence.
8. **Freeze or stop:**
   - **If the gate passes:** the last fold's model is a committed artifact, and a code constant
     names the report, the training cut-off and the SHA-256. A test ties code, artifact and report
     together.
   - **If it fails:** ROADMAP says B's one round failed on this data and P4 stays blocked. The
     report lists what was tried and ends with the owner's remaining options (§8).
9. `engine/package_readme.md` documents B, the labeler, the features, the new command and its
   performance. The full suite is green with 0 skipped, and CI stays green with scikit-learn
   installed.

## 7. Open questions for the analysis to settle (recommend, don't ask open-ended)

- **Vectorized labeler vs `sim`.** About 1.3M candidate rows. Recommended: a numpy labeler that
  works on float arrays over each symbol's next ≤ 7 bars, checked against `sim.step` on a
  one-order portfolio for a random-but-seeded sample of a few thousand rows in a test. Labels are
  training targets, not money, so float is fine; the portfolio itself still goes through `sim`.
  Confirm that the Decimal 4-dp bracket rounding is applied before the labeler sees the prices, so
  the labeler fills on the same limit the simulator would.
- **The model as `params`.** `ParamsSchedule.at(S)` returns a per-fold model wrapped in `BParams`.
  Settle what equality and hashing mean for it. `RunResult.params` and the report validation
  compare params; identity by fold index and a content hash is one option.
- **Prepared shape.** `prepare` can compute the raw per-symbol features for every (symbol, date)
  once, since they are param-independent. The cross-sectional ranks depend on the member set, so
  they are computed per `data_date` at pick time. Confirm this is fast enough over 2,200 traded
  sessions × 9 folds, or precompute ranks per date for the point-in-time member set (members are
  known per date, so this is still look-ahead-safe).
- **Tree determinism.** Verify that `HistGradientBoostingRegressor` is bit-identical across runs and
  `OMP_NUM_THREADS`. If it is not, apply the pre-registered switch (§3 Determinism). Do not tune
  around it.
- **Artifact format for a pass.** scikit-learn pickles are version-fragile. Recommended: pin the
  scikit-learn minor version, commit the pickle with its SHA-256, and also record the exact
  retrain recipe (data end, training cut-off, row count, label sum), so a re-fit reproduces it
  bit for bit on the pinned version. A test refits on synthetic data and checks the
  pickle/unpickle round-trip gives identical predictions.
- **A2 on the chart.** Recommended: read
  `docs/backtests/2026-10-02-strategy-a2-walkforward-equity.csv` when its data end equals the
  run's, otherwise recompute it through the P3b pipeline. Either way it is information, never
  gated.
- **Report layout.** Recommended: the main report holds per-fold summaries and tables, and a
  companion CSV holds the per-date picks or predictions only if it stays under a few MB. Otherwise
  leave it out.

## 8. If the gate fails: what the owner decides next (not part of P6a)

This rework does not decide it, but the report should end by naming the options plainly:
- **(b)** Accept SPY buy-and-hold as the honest champion for now. Seer can still paper-trade
  research strategies (P4 without real-money picks), and the home screen recommends no buys.
- **(c)** Revisit a design-§5 trade rule, for example the 5-day time stop, the 4 slots, or a longer
  holding horizon. That is a design change, so it needs the owner's explicit decision and a new
  handover. It is never done inside a strategy phase.
- **(d)** Strategy C (news + LLM veto) is forward-paper only by design §4, so it cannot pass a
  backtest gate. It does not unblock P4 under the current ROADMAP wording, and changing that
  wording is the owner's call.

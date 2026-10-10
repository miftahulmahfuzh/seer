# Package: seer_engine

**Location**: `engine` (src layout: `engine/src/seer_engine`)
**Last Updated**: 2026-10-10 (eodhd-survivorship-market phase 2 (P1-ENG-SLCU): an alias fill for the 200 survivorship-check members with no usable EODHD series under their store symbol — `seer_engine.survivorship_alias` resolves, offline, the other EODHD code each traded under (hint, company name, alias, class share, bankruptcy stem, vendor suffix), `survivorship_store --fetch-aliases` caches them under `engine/.cache/eodhd/alias/` only, and `--build` offers the accepted series by default (`--no-aliases` to opt out) and writes `alias_report.csv`; 128 of 200 filled, member-days 81.3% -> 89.0%. Before that, eodhd-survivorship-market phase 3 (P1-ENG-9L1M): an optional store file `market_series.csv` (VIX family, Treasury yields, gold) read point in time through the new `Market.series` (`MarketSeries`, `EMPTY_SERIES` by default) without moving the price fingerprint; the new cache-only `market_series` command writes it; `lab run` refuses a method that reads `series` on a store without them; and `lab unblock MNNNN --note ...` moves a `blocked-data` idea back to `idea`. Before that, eodhd-survivorship-market phase 1 (P1-ENG-8X1K): a separate, purpose-marked survivorship-check store, `engine/.research-sv`, built by the new `survivorship_store` command from the dev store plus cleaned EODHD bars for the members the dev store never served (`seer_engine.survivorship`); `lab run`, `lab test` and `lab remeasure` refuse it. Before that, hardgate-variant-and-blend-kin (P2-ENG-L1VT): the hard gate's fold half also scores the variant `lab promote` would pre-register on its own curve (D11, `hardgate.promoted_variant` / `variant_record`), and its kin half counts blend ingredients read from `trials.config_text` plus their family and ancestry (D12, `hardgate.ingredients`), which the walk-forward buy signal follows through `failed_kin` (D13). Before that, trial-reproducibility: every trial records its starting capital and its price fingerprint in the append-only `trial_provenance` table (schema 5, 152 trials back-filled by an exact rule); `lab remeasure` and `lab costs` re-run a recorded trial at its recorded capital and `hardgate.trial_deposits` de-funds by it; the hard gate refuses a comparison across price fingerprints, `lab walkforward` / `lab regime` warn, and `lab run` refuses a rebuilt dev store. Before that, lab-realistic-gate R2 (P1-ENG-FND7): `lab run` and `lab test` run every candidate on the owner's real funding and record a `trial_funding` row per funded trial)

## Overview

`seer_engine` is Seer's Python data pipeline. It writes the Neon (Postgres) tables the web
app reads: daily bars, USD/IDR FX and nightly `runs`, plus the engine's own bookkeeping tables
(point-in-time `universe`, `split_adjustments`, `backfill_log`). Phase 1 is the foundation:
the package, a plug-in CLI, migration 002, NYSE date arithmetic, idempotent DB write helpers
and removal of the web app's seeded demo data. Later phases add commands on top of it
(`universe`, `backfill`, `nightly`).

**Key Responsibilities:**
- One CLI (`python -m seer_engine` / `seer-engine`) whose subcommands are discovered from `seer_engine/commands/`
- Config from the environment, with the repo-root `.env.local` as a local fallback
- One transaction helper that every write goes through, with a whole-run `--dry-run`
- NYSE session arithmetic: which session's data is complete (`data_date`) and which session the next picks are for (`session_date`)
- Idempotent upserts for `bars` and `fx_rates`, where an identical re-run changes 0 rows
- The `runs` row lifecycle: one real row per target session
- Purging demo rows before the first real write
- Applying `db/migrations/*.sql`, sharing `schema_migrations` with web's `db:migrate`
- The pure fill simulator (`sim/`): order lifecycle, whole-share sizing, cash/equity and split recompute, shared by the backtest (P3) and nightly paper trading (P4)
- The pure strategy layer (`strategies/`): the `Strategy` protocol, numpy indicator windows and Strategy A with its frozen parameters, shared by the backtest (P3) and nightly picks (P4)
- The 10-year backtest (`backtest/`, `backtest` command): point-in-time market, the session loop around the simulator, SPY benchmarks, metrics identical to the web's, the in-sample grid, the out-of-sample gate and the committed report
- The Strategy A rework (P3b): `strategies.a2` (Strategy A's pre-registered variants V0–V3), an anchored yearly walk-forward (`backtest/walkforward.py`) that drives one portfolio whose params change by year, its report (`backtest/wf_report.py`) and the `backtest_wf` command
- Strategy B (P6a): `strategies.b` (an ML cross-sectional ranker on 15 ranked features and 3 SPY features, keeping A's bracket and passing on nights with no positive prediction), `strategies.b_model` (fixed-hyperparameter gradient-boosted trees, plus a ridge for information), a vectorized net-of-cost bracket labeler (`backtest/labels.py`), the B walk-forward over P3b's folds with a label purge (`backtest/b_walkforward.py`), its report (`backtest/b_report.py`), and the `backtest_b` command
- Trade rules as a value and a dev-window strategy search (P7a): `sim.rules` (`TradeRules`, with `DESIGN_V0` reproducing design §5 exactly) and a second pure engine, `sim.book` (signal exits, rebalancing, dividends, fractional shares, open entries, idle instruments); the `Allocator` protocol and the families F1–F11 (`strategies/allocator.py`, `f_index.py`, `f_rotation.py`, `f_factor.py`, `f_swing.py`); `backtest/book_runner.py`; a local, gitignored research store of pre-2015 history (`research.py`, `research_store` command); and a pre-registered registry run only on the development window (≤ 2015-10-16) by `backtest/dev.py`, `dev_report.py`, `registry.py` and the `backtest_dev` command, which writes the dev report and the P7b pre-registration
- Nightly paper trading (P4, paper-only by the owner's option (b), 2026-10-04): a frozen roster of four paper portfolios (`SPY` the champion and benchmark, `A`, `F4-MOM12-N20-TREND`, `F1-SPY-SMA200-M`) stepped one session at a time by pure night functions (`paper/bracket.py`, `paper/book.py`, `paper/benchmark.py`) that mirror the backtest runners' loop bodies; persisted in migration 003's tables by `paper/store.py`; driven by the `paper` command after `nightly`; proven equal to a one-shot `run_rules` / `buy_and_hold` replay by `paper_check`; each new pick stored with its evidence (the plain facts its formula used, `strategies/evidence.py`, migration 009) and optionally explained from that evidence by an LLM (`explain`). No real-money path exists, and design §1 is unchanged
- Strategy C on paper (P6): a fifth roster entry `C` whose picks are A's first 10 ranked candidates minus every symbol whose nightly news check did not say `allow`. `strategies.c` holds the pure part (the `NewsVeto` strategy, the frozen prompt `c-veto-v1`, the JSON verdict parser); `finnhub.py` reads company news and earnings dates; the `veto` command asks the LLM once per candidate before `paper` and stores every verdict and the headlines it saw in `news_vetoes` (migration 004); `paper` and `paper_check` read only stored verdicts, so the replay never re-asks the LLM. A failed or missing verdict is no trade (design §8). No backtest gate applies (design §1 item 5)
- The roster as data (roster-promotion-pipeline, phase 1): a paper portfolio is a `strategies` row, not a Python literal. Migration 006 adds the lifecycle (`status`, `paper_end`, `promoted_from`) and definition (`object_name`, `registry_id`, `gate_note`, `gate_applicable`) columns; `paper/roster.py` gains `RESOLVER` (the one code-side table mapping a stable object name to the live `Strategy` / `Allocator`) and `from_row` / `from_rows`, which build `RosterEntry` values out of rows; `paper/store.py` gains `read_roster_rows`. `ROSTER` is now `from_rows(SEED_ROWS)`, so the compiled roster and a database's roster travel the same builder, and the five pinned spec digests are unchanged. `veto` still reads the compiled `ROSTER`; `paper` and `paper_check` read the stored one (phase 2)
- The roster is read at run time, and retirement is a lifecycle (roster-promotion-pipeline, phase 2): `paper` and `paper_check` build their entries with `roster.from_rows(store.read_roster_rows(conn))` instead of the compiled `ROSTER`, so adding or replacing a horseman is a row change, not a code edit. `paper/store.py` gains `retire` and `set_paper_end`, the only two writers of the lifecycle columns; a `status = 'retired'` entry is a deliberate skip on the night (no orders, no equity snapshot, no `paper_state` step) and keeps every history row it ever wrote, while `paper_check` replays it like any other, so its record stays verifiable after it stops trading
- Promotion: the lab reaches the roster by command (roster-promotion-pipeline, phase 5): `commands/promote.py` turns a lab method's pre-registered `Candidate` into a `strategies` row (`status='active'`, `promoted_from=<method id>`, `registry_id` NULL, the full contract-C2 `params`, and **no** `paper_start` — the next paper night starts the clock the ordinary way, so a promoted strategy's record begins at its promotion). The row is read back and rebuilt through `roster.from_row` inside the same transaction, so a row the night would refuse never commits; `--retire <id>` runs phase 2's `store.retire` in that transaction, making a swap atomic. `lab/store.py` gains `record_promotion` (an append-only, idempotent lab note, moving the method's status only along the existing `('test-passed','paper')` edge) and `PROMOTION_MARKER`. `backtest/registry.py` is deliberately never touched (Decisions D1)
- Honest comparison (roster-promotion-pipeline, phase 3): `paper/compare.py` is the pure, common-window, risk-adjusted comparison of the paper equity curves — every ranked figure is computed over the one window every ranked strategy shares (the intersection of snapshot dates, not `[max(start), min(end)]`), the window travels with the figures, inception-to-date is carried separately and never ranked, and a strategy that cannot join the window is an explicit `insufficient` row with a reason rather than a silent omission. The read-only `compare` command is its one impure edge
- `FND` joins the roster (roster-promotion-pipeline, phase 6): a sixth entry, `FND · Fundamentals` (top 20 by SEC filing factors, monthly; `object_name = 'FUNDAMENTAL'`, `rules_id = 'monthly-hold'`, the book engine, `sort = 6`, `promoted_from = 'M0005'`, `registry_id` NULL), seeded by migration 007 and put on the live board by phase 5's `promote --method M0005 --candidate M0005-ALL --id FND --lab-status-stays` — the first promotion through the new lab → roster path rather than around it. Its `gate_note` says out loud that it **failed** its M0005 dev-window gate: passing a backtest gate has never been this roster's admission criterion (Decisions D5), and the gate binds the real-money decision, not paper membership. It is also the roster's first `MarketAware` object, which is why `paper/book.py` and `paper/replay.py` gained the prepared dispatch below. The five pre-existing spec digests are unchanged and `MAX_LOOKBACK_BARS` is still 253
- Two windows, two stores (build-promotion-path, phase 2): the research window became a parameter on the store half. `build_store` / `load_store` / `refresh_fundamentals` each take a keyword `window=` defaulting to `DEV_WINDOW`, and a store declares its own window in three **optional** manifest keys (`window_name`, `window_start`, `window_end`) that a dev build never writes — **absent means dev**, so `engine/.research`'s manifest stays exactly the nine `MANIFEST_KEYS` it was sealed with and its fingerprint cannot move. `research_store --test-window` builds the P7b test-window store (2015-10-19..data end) into `engine/.research-test` (gitignored); `load_store` refuses a dev store where a test store is expected and the reverse, before it reads a single data file. `MANIFEST_KEYS` is unchanged at nine, no test-window look is spent, and no lab state changes
- Pre-registration, the half a database cannot enforce (build-promotion-path, phase 3): the lab gets **one** look at the test window per configuration, and `UNIQUE(config_digest, window)` on `trials` enforces the *count* but not *which* configuration the look is spent on. `lab/prereg.py` owns the committed file that does — `docs/lab/prereg/MNNNN.md`, a strict `key: value` block then prose — with its writer, its parser (`parse(render(p, name)) == p` exactly) and the gate `lab test` calls before it looks (`require_committed`, `check_digest`). `lab promote <method>` writes that file for the method's best dev-eligible variant by MAR (`lab.store.best_dev_eligible`) and moves the method `dev-eligible -> promoted`; it loads no research store, runs no backtest and inserts no `trials` row, so pre-registering costs no look. A pre-registration is written once and never rewritten: a better variant found later is a new method with its own dev trials, not an edit to the file
- Spending the look (build-promotion-path, phase 4): `lab test <candidate>` is the one counted look at the test window, and the last step before the roster. `lab/runner.py` gains an appended test-window half — `Tested`, `resolve_candidate`, `preflight_test`, `test_trial_row`, `run_test` — and `commands/lab.py` the `test` subcommand (with `--dry-run`, `--store`, `--roster-id`). It refuses, in this order, a method that is not `promoted`, a method file that has changed since its dev trials ran, a missing or uncommitted pre-registration, a pre-registered digest that has drifted, a configuration with no recorded dev trial, and a configuration that has already had its look — the last enforced in the database by `UNIQUE(config_digest, window)`, not only in the command — and it refuses a dev research store *by name* before anything is loaded. A run appends exactly one `trials` row with `window = 'test'`, which **does not move the lab's N** (`dev_trial_count` and `dev_daily_sharpes` stay dev-only, so a test look is a look, not a search); DSR is recorded and never decides the verdict, because a pre-registered look has no selection among results to deflate. The method ends at `test-passed` or `test-failed`, both final, and a pass prints a ready-to-run `seer_engine promote ...` line that hands off to phase 5's existing paper-roster path. `lab status` now lists `Test-passed` and `Test-failed` alongside `Promoted (pre-registered)`; against the real lab `test-window looks used` still reads 0 — this phase builds the mechanism and spends nothing
- The clobber guard knows a store by its content, not by its path (research-store-clobber-guard, the set's single phase): `commands/research_store.py`'s two `_same_dir` guards compare the `--store` path against `research.STORE_DIR` / `research.TEST_STORE_DIR`, which are derived from the **running module's own location** — so a `--test-window` build aimed at another checkout's or worktree's `engine/.research` was not refused, and a build replaces the whole directory. The **build path only** now also asks the target what it is: `_declared_window_or_none` wraps `research.declared_window`, and a declared window that disagrees with `--test-window` exits 2 before a single symbol is downloaded. The answer comes from the target's own `manifest.json`, so it holds for a store anywhere on the machine; `None` means *undecidable*, never *wrong*, so a missing, empty or unparseable target falls through and the first build of all still works. The two path guards are byte-for-byte unchanged and still fire first, and `--verify`, `--coverage` and `--refresh-fundamentals` are untouched — they read a store rather than replace one
- A trial keeps the inputs of its own verdict (lab-luck-gate, phase 2): `lab/store.py` gains an additive, append-only `trial_moments` side table (`trial_n` primary key, then `sr_daily`, `t`, `skew`, `kurt`, `var_trials`, `n_at_run`, `measured`) held append-only by two triggers, `trial_moments_no_update` and `trial_moments_no_delete`; `SCHEMA_VERSION` moves 2 -> 3 and `_migrate` becomes a version ladder (`_v1_to_v2` / `_v2_to_v3`), so a v1 database reaches v3 in a single open. Its surface is `store.MomentsRow`, `MOMENTS_COLUMNS`, `insert_moments()` and `moments_of()`; `lab/runner.py` gains `Ran.moments`, with `trial_rows` hoisting its `daily_moments` call so the moments are captured and written in the **same transaction** as the trial they judged. The why is the load-bearing half: `trials` is append-only and a row's `dsr` is frozen at the N of its run date, so a verdict could never be recomputed — `trial_moments` keeps the exact inputs `dev.deflated_sharpe` was fed, so phase 3's `lab remeasure` and phase 4's derived verdict can re-judge a recorded trial at the current N without re-running the backtest. It changes no verdict and adds no `trials` row: the same `dev.deflated_sharpe` call on the same six arguments, `dsr`, `failed`, `eligible` and `n_trials_at_run` unchanged, `trials` still append-only, `test_looks` still 0
- Every roster entry carries its lab provenance (lab-luck-gate, phase 6): a paper entry that came from a recorded lab candidate now says in code which lab method and variant it is, the lab status it was admitted under, and on what basis — `test-passed`, or `owner-override` with a one-line reason. `paper/roster.py` gains `Basis` / `BASES`, the frozen `LabProvenance` dataclass (which refuses an override with no reason), the `LAB_PROVENANCE` table keyed by roster id, and a `lab_provenance` field on `RosterEntry` that `from_row` fills from that table. It sits **outside** the spec, exactly where `status`, `paper_end`, `gate_note` and `gate_applicable` already sit, so no `spec_digest` moves and no entry is retired. `lab/store.py` gains `PROMOTION_BASES` and `promotion_basis(status)`, and `record_promotion` takes `basis=` / `reason=`, writes both into the method's `# Promotion` analysis section, and **refuses an unexplained owner override**. `promote` gains `--lab-override-reason`, requires it whenever the method is not at `test-passed`, and prints the `LAB_PROVENANCE` line to add in the same commit. The admission *policy* is unchanged (Decisions D3: paper membership has never required a gate pass, and the lab's design §3/§6 reading that a test pass leads to the roster is a *sufficient*, never a necessary, route); what changed is that the basis stopped being prose in a commit message. `tests/test_paper_roster.py` checks every provenance line against the committed `lab/lab.sqlite`
- The verdict is derived, under one policy, at evaluation time (lab-luck-gate, phase 4): a dev trial's eligibility stopped being a column read back off the row and became something `lab/store.py` *decides* when asked. `store.verdict(conn, trial)` re-derives the four threshold owner conditions from the trial's own recorded columns against the live `tuning.MAX_DRAWDOWN` / `tuning.MIN_PROFIT_FACTOR` / `dev._MIN_TRADES` (`owner_failures`), carries only `owner inputs` from the record — the one condition no constant re-decides — and settles the luck test on that trial's DSR **at the gate's current N** (`dsr_at`, exact from `trial_moments` or recovered by inverting the recorded DSR through `recover_dsr`, deflated on both routes by today's `dev_sharpe_variance`). A DSR that cannot be evaluated *fails* the luck test, so nothing is admitted for being unmeasurable. The gate's two constants are `store.DSR_MIN` (0.95 -> 0.90, the owner's stated risk appetite) and the new `store.DSR_POLICY = "all-trials"`, the single name that decides N; `store.gate` / `pending_gate` resolve it, and `runner.trial_rows` is a two-line delta onto `pending_gate`, so a trial recorded tonight is judged by the same bar as one recorded six weeks ago. Recorded rows keep the labels of the bars they were judged under — all 110 say `DSR >= 0.95` and `max DD <= 15%` — so every reader goes through `is_luck_label` and `owner_failures` rather than comparing to `DSR_LABEL` or parsing `failed`. `TRANSITIONS` gains exactly one new edge, `('rejected','dev-eligible')`, reachable only through the twice-guarded `reevaluate_method` behind the new `lab reevaluate` command. Nothing in `trials` is written, the lab's N does not move and `test_looks` is still 0; `lab/lab.sqlite` takes an additive, idempotent migration (schema_version 3) and `web/data/lab.json` is re-exported from it. Net effect: at (N = 110, DSR >= 0.90, max DD <= 20%) exactly three trials are eligible — `M0022-W-TV14`, `M0022-W-TV16` and `M0020-W-NOSTOP` — so the promotion path is reachable for the first time, and `(all-trials, 0.95, 15%)` reproduces the previous verdicts exactly
- The second lever is built, measured and not pulled (lab-luck-gate, phase 5): the luck bar has two levers — the threshold `store.DSR_MIN` and the N that `store.DSR_POLICY` resolves to — and Decision D1 moved only the first, deliberately. `commands/lab.py` gains the read-only `lab luck` (`_HANDLERS["luck"]`), the instrument that shows what moving the second would do **against the committed database, without editing the constant and re-running anything**: one column per named N policy and one per repeatable `--at N`, each recorded DSR re-evaluated there by inverting that trial's own per-trial constant through `store.recover_dsr`, so the `recorded` column reproduces the database exactly and every other column moves nothing but the multiple-testing count. Per policy it prints the N and the evidence for it, the daily hurdle `SR*`, and which candidates clear the bar — on the committed lab exactly three do at the live N = 110 — above the trial-Sharpe variance the deflation rests on; each policy's `evidence:` line is read generically off its `npolicy.NCount`, so the participation ratio and mean pairwise correlation behind an N cannot go stale in this output. In the same phase `lab status` stops hiding an empty promotion path: `_promotion_path` now **always** prints every step from `Dev-eligible` to `Paper`, an empty one with `_empty_reason`'s one sentence saying why (and, for `dev-eligible`, which bar is holding the closest candidate), alongside a `Promotable now` list ranked by MAR, the methods eligible on the evidence but held by the status machine, `Test-window looks used: k` (design §3), and the D1b ratchet warning — which names the N at which the best passing candidate's DSR falls back under the bar and how many more dev trials that is, because more exploration re-closes the gate the threshold just opened. Both commands are strictly read-only, proven by measurement rather than asserted: `lab/lab.sqlite`'s md5 is unchanged across both and `store.test_looks` still reads 0; since trial-reproducibility SCHEMA_VERSION "5" with the append-only trial_provenance table (initial_idr, price_fingerprint, source) -- ProvenanceRow, insert_provenance(), provenance_of(), back-filled by the 4 -> 5 migration
- Gotrade's real fees as a cost model (Sean plan, phase 6): `sim/costs.py` holds `GOTRADE`, a schedule of four dated fee regimes fitted to the owner's 30 Gotrade order receipts (`tests/fixtures/gotrade_fees.json`, fee columns only). `TradeRules` gains `cost_model: Literal["flat", "gotrade"] = "flat"`, a lever in `LEVERS_SINCE_PINS`, so at "flat" no registry, lab-trial or paper-spec digest moves (`tests/test_cost_model_pins.py` recomputes every committed lab digest byte for byte). Under "gotrade" the book engine prices every fill from today's regime, and the lab's SPY benchmark (`backtest.dev._run` → `spy_curves`) pays the candidate's own cost model. (The paper benchmark stayed flat until phase 12 of the Gotrade fee rebuild wired it, below)
- Real fees become the lab's rule (Sean plan, phase 7): `sim.rules` gains the two real-fee presets `MONTHLY_HOLD_FRAC_GOTRADE` (`monthly-hold-frac-gotrade`) and `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` (`monthly-rank-weekly-resize-frac-gotrade`), appended to `PRESETS` so `promote` can map a real-fee winner to a preset of its own id; they name `cost_model` in their canonical form and digest apart, while every flat preset still omits it. `lab/runner.preflight` now also raises `lab/real_costs.real_cost_problem`: from **M0031** on (`REAL_COST_SINCE = 31`) every variant must be a book rule set at `cost_model="gotrade"`, and methods up to M0030 keep their flat cost and pinned digests. For those older methods the new report-only `lab costs MNNNN` re-runs the best recorded dev variant (by MAR, or `--candidate`) at both cost models and journals one `observation` — no `trials` or `trial_moments` row, no status change, so the lab's N and `test_looks` do not move. On the Sean side, `sean/calibrate.py` and the read-only `sean calibrate` replay `sim.costs.fee_parts` over every stored `sean_orders` receipt (on its WIB date) and exit 1 when an order since the current fee regime is off by more than a cent in any part — the signal to add a new dated regime to `sim/costs.py`; since trial-reproducibility a trial_provenance row per trial in the same transaction, and recorded_capital() for every re-run of a recorded trial
- The rebuilt roster, and the wiring layer (GOTRADE_FEE_REBUILD, phase 12): every live entry is replaced by a successor paying Gotrade's **measured** fees — `SPY-GT`, `C-GT`, `RMW-FR-GT`, `RAW-FR-GT`, `MOM-FR-GT`, `MVW-FR-GT` — as **new ids with fresh paper clocks** (`cost_model` is a `LEVERS_SINCE_PINS` lever, so editing a started entry would move its digest and `store.check_digest` would refuse its next night), with the six predecessors **retired, not deleted**. Migration 017 writes them; `paper/roster.py` gains the six ids, `BENCHMARK_SYMBOL`, `OWNER_FUNDING`, `PRE_FUNDING_IDS`, `BENCHMARK_COST_MODEL` / `benchmark_cost_model`, and a `spec` whose `funding` and benchmark cost keys are conditional so no pinned digest moves. The wiring: the night passes each entry's **own** `rules` into `settle_bracket` / `decide_bracket` / `repick`, `_step_benchmark` loads `SPY-GT` at its roster-stated cost model, the night accrues and credits the owner's contribution schedule (10,000,000 IDR to start, +5,000,000 IDR on the 25th) raising cash and equity together on all three engines, `paper/replay.py` replays the stored dated deposits instead of hard-coding `DESIGN_V0`, and `promote` dispatches the engine on `sim.rules.is_bracket`. `PAPER_PAUSED` stays `'true'`: the rebuilt roster sits inert, no `paper_start` is written and no session is stepped until the owner flips the switch himself
- The gate counts the looks the data supports (lab-realistic-gate, R1): `store.DSR_POLICY` and `npolicy.DEFAULT_POLICY` move `"all-trials"` -> `"methods"`, so the luck test deflates by the number of **distinct methods** the lab has looked at — **N = 28** on the committed `lab/lab.sqlite`, not the 126 dev trial rows — floored at the measured participation ratio (`max(distinct_methods, ceil(participation_ratio))`; `ceil(2.338) = 3`, so the floor does not bind). The reason is not that 126 is a big number: a lab of 126 rows holds 28 ideas, and mean pairwise correlation 0.612 across them says the row count asserts an independence the curves contradict. The consequence that matters operationally is **locality** — a variation twin of an existing method adds 0 to N and a brand-new method adds 1, so re-running one method no longer perturbs every other method's verdict, which is what made the all-trials gate unusable as exploration continued. Nothing recorded is rewritten (`trials` still 128 rows, `test_looks` still 2, every row keeps the label of the bar it was judged under): the verdict is *derived*, so only the published verdicts move — six methods go `rejected` -> `dev-eligible` (M0002, M0007, M0011, M0019, M0024, M0030), `dev-eligible` 2 -> 8 and `rejected` 27 -> 21. Two consequences elsewhere in the package: `remeasure.batches_of`'s second guard had to widen from an equality to a bounded range, because the equality *was* the all-trials projection and would have refused every batch recorded under any other policy; and the lab test modules whose fixtures stamp `n_trials_at_run` with their own dev row count (`test_lab_prereg.py`, `test_lab_status.py`) now pin `DSR_POLICY = "all-trials"` in an autouse fixture, naming the assumption they already encoded rather than inheriting whatever the shipped constant happens to be. Shipped in the same phase: `lab --help`, dead on `main` since a bare `%` entered an argparse `help=` string, is fixed — see the Command contract; since trial-reproducibility both paths re-run at runner.recorded_capital, and plan_capital() refuses a set recorded at two capitals
- The search is run on the owner's real money, and a deposit stops counting as a return (lab-realistic-gate, R2): `lab run` and `lab test` now fund every candidate with `sim.contributions.OWNER_MONTHLY` — 10,000,000 IDR to start and +5,000,000 IDR on the 25th of every month — and record one `trial_funding` row per funded trial inside the **same** `BEGIN IMMEDIATE` that records the trial, so the gate's money-weighted branch judges a newly run method on `mwr` against a dollar-cost-averaged SPY instead of on a total return that counts the owner's own deposits as growth. New in `lab/runner.py`: `OWNER_SCHEDULE_TEXT` (built from `OWNER_MONTHLY` rather than typed out, so a recorded row can never state a schedule the run was not fed), `recorded_contributions(conn, trial_n)` and `Ran.funding`; `trial_rows` gains keyword-only `deposits=` / `schedule=` whose defaults reproduce its old output byte for byte. **Every re-run path resolves its funding through `recorded_contributions`** — `lab remeasure` and `lab costs` reproduce a recorded trial on the funding it actually ran on, and `remeasure.measure` refuses outright a plan that mixes funded and unfunded trials, because one `dev.run_registry` call runs every candidate on one schedule and no schedule reproduces both. The second half of the phase is the correction funding made necessary: a deposit is not a return, and two gate conditions were being computed off raw equity. `book_runner._daily_returns` and `_year_returns` are now cashflow-adjusted (`cur / (prev + flow_t) - 1`, through the new `metrics.flow_map`) and `metrics.strategy_metrics` measures a funded run's `max_drawdown` on the time-weighted wealth index. Measured on the smoke fixture, uncorrected: an annualized Sharpe of 2.6524 for a book whose honest Sharpe is 0.2620 — a 10.1x inflation feeding `trials.dsr` and the luck test — and a max drawdown of 0.0796 against an honest 0.1055; corrected, 0.2904 and 0.1034. `total_return` and `cagr` are left contaminated deliberately, because they are the recorded shape of the curve that readers of the 128 historical trials depend on and `mwr` stands beside them with the honest number. Nothing recorded moves: the 128 pre-existing trials have no `trial_funding` row, `store.funding_of` still answers None for every one of them, and an unfunded run takes the original expressions verbatim and is byte-identical
- Recorded trials reproduce, and the gate compares like with like (trial-reproducibility): the lab could not re-run its own record — `lab costs M0011` read +545.3% where trial #90 records +660.2%, and the 152 trials carried three store fingerprints. Measured, the store never moved its prices (the three fingerprints differ only in `fundamentals.csv`); what moved was `INITIAL_IDR`, 20,000,000 -> 10,000,000 in `d79fc83`, which no trial recorded and which whole-share rounding makes result-moving. `lab/store.py` schema 5 adds the append-only `trial_provenance` table (`initial_idr`, `price_fingerprint`, `source` `'recorded'`/`'backfill'`), written by `lab run` / `lab test` in the trial's own transaction and back-filled for every older trial (lump-sum -> 20M, funded -> 10M, exact on all 152); `research.price_fingerprint_of` hashes the four price files only. Every re-run of a recorded trial runs at `runner.recorded_capital`, which is how `lab remeasure M0007`, `M0011` and all 54 `H-P7A` seed trials reproduce exactly on today's store with `INITIAL_IDR` unchanged. Comparability is keyed on the price fingerprint, not the store fingerprint: `hardgate.fold_record` refuses a mismatch or an unknown, `lab walkforward` / `lab regime` warn, and `lab run` refuses a dev store whose price fingerprint is not the benchmark's. It strands 0 trials and changes 0 verdicts today. Recovered `trial_moments` were deliberately not written to the committed lab (they would move `H-P7A-F9` and two DSRs; that judgement belongs to the explore loop)
- A second dev-window store that measures the survivorship gap and can never record a trial (eodhd-survivorship-market, phase 1): `engine/.research` serves 539 of the 1061 symbols it requested, and most of the other 522 are companies that died. The paid EODHD month cached their raw history; `seer_engine.survivorship` (pure) cleans it into the dev store's own bar conventions, and `commands/survivorship_store.py` writes `engine/.research-sv` (gitignored) — the dev store's lines byte for byte plus the cleaned symbols, offline from the cache, with **its own price fingerprint**. The dev store stays byte-identical. The new manifest is marked `"purpose": "survivorship-check"` (`research.PURPOSE_KEY`, optional, unhashed, never written by `build_store`), surfaced as `ResearchData.purpose` / `research.declared_purpose()`, and `lab run`, `lab test` and `lab remeasure` refuse a marked store (exit 2) before any trial, moment or look is written: the store is report-only, never a trial source. Real build: member-day coverage 58.6% -> 81.3%; of 522 cached symbols 187 kept, 73 repaired, 62 trimmed, 200 dropped; 239 members still missing
- The members phase 1 could not fill, filled under the code they really traded under (eodhd-survivorship-market, phase 2): 200 cached symbols came back with nothing on their member days because the ticker now belongs to someone else (`DOW` is Dow Inc since 2019) or the company traded under another code (WorldCom is `MCWEQ`). `seer_engine.survivorship_alias` lists candidate codes per member from EODHD's cached symbol lists — a hand-checked hint (`data/eodhd_alias_hints.csv`), the normalized company name, `ticker_aliases.csv`, the class-share spelling, the bankruptcy stem, the vendor's `_old` / `_oldN` / `N` suffixes — and accepts one only when its series has at least `MIN_MEMBER_ROWS` rows on the member's own index days and passes the same cleaning; two fitting candidates that are different price series resolve to none. `survivorship_store --fetch-aliases` is the only network path and writes under `engine/.cache/eodhd/alias/` only; `--build` offers the accepted series to `plan_build` as `extra_sources` (cleaned like any other, `best_of` keeps the better) and writes `alias_report.csv`. Real build: 128 of 200 filled (`source` `eodhd-alias` in `cleaning_report.csv`), member-day coverage 81.3% -> 89.0%, members still missing 239 -> 111; the SV store's price fingerprint moved to `60adae1b…` (was `bc5ba895…`). The dev store is untouched
- Market-wide series an allocator can read, point in time (eodhd-survivorship-market, phase 3): `research.MARKET_SERIES_FILE` (`market_series.csv`, `series,date,value`) joins `OPTIONAL_DATA_FILES` as its third entry, never `DATA_FILES`, so writing it moves a store's full fingerprint and never the price fingerprint every recorded trial is compared on. `load_store` reads it into `Market.series`, a `backtest.market.MarketSeries` (`value_on`, `upto`, `names`, `first_date`; every read sees only rows dated on or before `data_date`); a market built any other way carries `EMPTY_SERIES`. `commands/market_series.py` reports and (`--refresh`) writes the ten series from the EODHD cache only: the VIX family in points, `IRX` as a yield in percent, `TNX` / `FVX` / `TYX` divided by 10 into percent, VIX3M spliced from `VXV` where `VIX3M` has no close, gold in USD/oz, NYSE sessions only, clipped to the store's window. An allocator declaring `market_fields = ("series",)` is refused by `runner.preflight_data` on a store with no series. `lab unblock MNNNN --note ...` is the command for the existing `blocked-data -> idea` transition

## Layout; since trial-reproducibility trial_deposits() de-funds by the recorded capital, and the price-fingerprint comparability rule (D10): mismatches(), comparability(), fold_record() refusing an incomparable trial, pin_dev_store() for `lab run`

```
engine/
  pyproject.toml            package seer-engine 0.1.0, python >=3.11, script seer-engine
  .gitignore                *.egg-info/, build/, dist/
  src/seer_engine/
    __init__.py             __version__ = "0.1.0"
    __main__.py             python -m seer_engine -> cli.main()
    cli.py                  parser, command discovery, logging, exit codes
    config.py               env + dotenv loading
    db.py                   connect(), transaction()
    http.py                 get_json() with retries, redact()
    dates.py                NYSE sessions, RunDates
    demo.py                 demo-data purge
    universe.py             read-only point-in-time membership queries
    prices.py               pure Bar, PRICE_QUANTUM, to_decimal (no psycopg)
    bars.py                 re-exports prices; to_volume, make_bar, upsert_bars()
    fx.py                   Frankfurter USD/IDR fetch, upsert_fx()
    yahoo.py                yfinance download + frame parsing, BRK.B <-> BRK-B (phase 3)
    runs.py                 start_run / finish_run / fail_run
    research.py             local research store: build_store() / load_store() / refresh_fundamentals(), each with a keyword window=; test_window(), latest_session(), declared_window(); the D9 end-of-window guard (impure; P7a, windowed in build-promotion-path phase 2); since trial-reproducibility price_fingerprint_of() over the four price files and ResearchData.price_fingerprint; since eodhd-survivorship-market the optional manifest `purpose` key (PURPOSE_KEY, SURVIVORSHIP_PURPOSE, SV_STORE_DIR, declared_purpose(), ResearchData.purpose); since phase 3 the optional market_series.csv (MARKET_SERIES_FILE, MARKET_SERIES_HEADER, MARKET_SERIES_NAMES, market_series_lines(), refresh_market_series(), read into Market.series by load_store)
    survivorship.py         pure (bar a cache reader): cleans cached EODHD series for the members the dev store never served -- SourceSeries, read_series(), clean_symbol(), best_of(), coverage_by_year() (eodhd-survivorship-market phase 1)
    survivorship_alias.py   offline alias resolution for the members with no usable EODHD series under their store symbol: load_sources(), candidates(), choose(), resolve(), Resolution; fetch() (the one network path, injected eodhd.Client, writes <cache>/alias/ only); alias_sources() -> SourceSeries for plan_build; report_rows()/report_text() for alias_report.csv (eodhd-survivorship-market phase 2)
    delisting.py            delisting stress: measure_hazard() / survivors() / draw_deaths() / kill() / stressed();
                            pure given its Random, reads no clock and no I/O, imports no lab module
                            (delisting-stress-roster-rules phase 1)
    dividends.py            Massive cash dividends (CD + SC) per ex-date, upsert into `dividends` (P4)
    llm.py                  Anthropic-compatible Messages call for `explain` (P4) and `veto` (P6, with temperature/thinking/max_tokens per call)
    finnhub.py              Finnhub company news and earnings calendar, rate-limited, key in a header only (P6)
    sim/                    fill simulator: pure, deterministic, Decimal-only (P2)
      __init__.py           public surface; import everything from seer_engine.sim
      model.py              constants, money helpers, Order, Portfolio, Event, Snapshot, StepResult
      lifecycle.py          step(), close_unpriced()
      sizing.py             Pick, Rejection, SizingResult, size_picks()
      split_adjust.py       apply_split()
      costs.py              Gotrade's measured fee schedule: FeeParts, FeeRegime, GotradeSchedule, GOTRADE, fee_parts(), gotrade_cash(), gotrade_shares_for() (Sean phase 6)
      contributions.py      the owner's recurring deposit as a value: ContributionSchedule, OWNER_MONTHLY, MAX_DAY_OF_MONTH, Contributions, credit_for (plan phase 5)
      rules.py              TradeRules, DESIGN_V0, V0_BOOK, the presets, the rank/resize cadence split (P7a)
      book.py               the book engine: Target, Book, Position, Fill, Trade, step_book(), close_book_unpriced() (P7a); apply_book_split(), BookSplit (P4)
    paper/                  nightly paper trading (P4); every module but store.py is pure
      __init__.py           docstring only
      roster.py             the roster builder: RESOLVER, Row / RosterRow, from_row() / from_rows(), SEED_ROWS -> ROSTER (six entries), active(), canonical spec text, digest, backtest_gate; LabProvenance / BASES / LAB_PROVENANCE, the admission record (lab-luck-gate phase 6)
      bracket.py            settle_bracket(), decide_bracket(): run_backtest's loop body for one session
      book.py               settle_book(), decide_book(): run_book's loop body for one session, incl. the MarketAware prepared branch (phase 6)
      benchmark.py          BenchmarkState, start_benchmark(), split_benchmark(), step_benchmark(): buy_and_hold for one session
      replay.py             the pure comparison behind paper_check
      compare.py            common-window, risk-adjusted comparison of the equity curves: Window, Performance, Row, Comparison, compare(), render(), as_json() (phase 3)
      store.py              load/save paper state, windowed market, splits and dividends queries, news verdicts (impure)
    strategies/             strategy layer: pure; float64 indicators, Decimal picks (P3)
      __init__.py           re-exports the public names of base, a, a2 and b (never b_model, so importing the package does not load scikit-learn)
      base.py               History, history_from_bars(), Strategy protocol
      indicators.py         sma / wilder_rsi / wilder_atr / mean_dollar_volume / mean / stdev_return windows, rolling()
      a.py                  Strategy A: AParams, DESIGN_PARAMS, STRATEGY_A_PARAMS (frozen), StrategyA
      a2.py                 Strategy A2 (P3b): A2Params, VARIANTS V0-V3, regime_on, STRATEGY_A2_PARAMS, StrategyA2
      b_model.py            Strategy B's model (P6a): fit_tree / fit_ridge, BModel (digest identity), importance, dumps / loads
      b.py                  Strategy B (P6a): 18 features, rank01, candidates, BParams, picks > 0, FrozenModel, STRATEGY_B_FROZEN, StrategyB
      c.py                  Strategy C (P6): CParams, STRATEGY_C_PARAMS, the frozen prompt c-veto-v1, candidates(), NewsVeto, parse_verdict()
      allocator.py          Allocator protocol (target weights), target_from_close, month_end_closes, PICKS / BLEND / VOLTARGET (P7a); MarketAware protocol + prepare_for() (edgar-fundamentals)
      f_index.py            F1/F10 TIMING (trend-timed index), F11 CALENDAR (turn of month) (P7a)
      f_rotation.py         F2/F3 ROTATION (dual momentum, sector rotation) (P7a)
      f_factor.py           F4/F5/F6 FACTOR (momentum, low vol, momentum + low vol) on index members (P7a)
      f_swing.py            F7 SWING (longer-horizon RSI(2) mean reversion, signal exits) (P7a)
      evidence.py           per-pick evidence (why-this-pick-pipeline phase 1): EVIDENCE keyed by paper.roster.RESOLVER name -> (market, params, data_date, symbols) -> {symbol: plain facts}; evidence_for(), has_evidence(). Pure; never read by any decision
    backtest/               10-year backtest (P3) and walk-forward (P3b, P6a); every module but io.py is pure
      __init__.py           docstring only
      market.py             Membership, Market: bars, universe, FX and the point-in-time SEC fact panel in memory; EMPTY_FUNDAMENTALS, Market.with_fundamentals() (edgar-fundamentals); MarketSeries, EMPTY_SERIES, Market.series, Market.with_series() (eodhd-survivorship-market phase 3)
      runner.py             run_backtest(), RunResult, survivorship(), ParamsSchedule (P3b)
      benchmark.py          SPY buy-and-hold, price-only and total-return
      metrics.py            Metrics, strategy_metrics(), checklist() (web/lib/metrics.ts parity), metrics_through() (P3b); money_weighted_return(), external_cashflows(), flow_map() for a run that received deposits (lab-realistic-gate R2)
      tuning.py             windows, the 81-run grid, select(fallback=), gate()
      walkforward.py        folds, 324 combinations, tune(), select_fold(), walk_forward(), diagnostics(), gate_p3b() (P3b)
      report.py             BacktestReport, render_markdown(), equity_csv(), equity_svg()
      wf_report.py          WalkForwardReport, machine lines, Markdown, equity/grid CSVs, two SVGs (P3b)
      labels.py             vectorized bracket labeler: net-of-cost label and resolution date per order (P6a)
      b_walkforward.py      candidate table, purge, per-fold fits, probe, B / B-linear runs, calibration, gate_p6a() (P6a)
      b_report.py           BReport, machine lines, Markdown, equity CSV, SVG (P6a)
      book_runner.py        run_book(), run_rules() (DESIGN_V0 -> run_backtest unchanged), BookResult, RunStats, run_stats() (P7a)
      window.py             Window(name, start, end), WINDOW_NAMES: the session range a run is bound to (P7a)
      dev.py                DEV_WINDOW / DEV_END guard, Candidate, candidate_window(), run_registry(), D8 finalists(), deflated_sharpe() (P7a)
      dev_report.py         DevReport, Markdown, rows/curves CSVs, frontier SVG, P7b pre-registration (P7a)
      registry.py           REGISTRY: the append-only candidate registry (P7a)
      io.py                 Neon loader + bar cache, dividends CSV, report writers write_report() / write_wf_report() / write_b_report() / write_dev_report(), write_model_artifact() (impure)
                            load_panel() + fact cache, read_facts() -- the tree's one declared impure backtest edge for fundamentals (edgar-fundamentals)
    fundamentals/           raw SEC XBRL facts -> point-in-time panel: pure, like `strategies` (edgar-fundamentals)
      __init__.py           public surface; `sue` stays a module, never re-exported
      ladder.py             LADDER_TAGS, the ingest allowlist the impure ingest command imports; per-metric tag preference order
      panel.py              Fact, Snapshot, FundamentalPanel.as_of(symbol, t) -> Snapshot (the one read surface), EMPTY_PANEL (what Market.fundamentals defaults to), FACT_COLUMNS (the 12-column projection contract)
                            filed <= t only, never period_end; tiebreak (filed desc, rung asc, accn desc) per period; restatements preserved, never overwritten; flow metrics annual, not TTM; gross profit reported -> derived (Revenues - CostOfRevenue, same fiscal period end) -> none, never zero, never partial
      sue.py                standardized unexpected earnings on the seasonal random walk EPS_q - EPS_{q-4}, scaled by the dispersion of prior surprises; MIN_QUARTERS = 9
    lab/                    the method lab (docs/plans/2026-10-04-method-lab-design.md); only store.py and prereg.py touch the disk
      __init__.py           docstring only
      method.py             a lab method file: METHOD, Candidate, METHOD_ID, discover(), config_digest(), source_sha()
      store.py              lab/lab.sqlite: committed and append-only; methods, trials, ideas, insights; TRANSITIONS, record_promotion(), best_dev_eligible() (build-promotion-path phase 3); PROMOTION_BASES, promotion_basis() and record_promotion's basis= / reason= (lab-luck-gate phase 6); the append-only trial_moments side table with MomentsRow, MOMENTS_COLUMNS, insert_moments(), moments_of(), SCHEMA_VERSION now "3" and the _v1_to_v2 / _v2_to_v3 migration ladder (lab-luck-gate phase 2); the **derived verdict** (lab-luck-gate phase 4) — DSR_MIN and DSR_POLICY as the gate's two constants, LUCK_LABEL_PREFIX / is_luck_label(), recorded_labels(), OWNER_INPUTS_LABEL / owner_failures(), sr_star(), recover_dsr(), dev_sharpe_variance(), dsr_at(), Gate / gate() / pending_gate(), Verdict / verdict(), best_dev_eligible() now judging on it, and the twice-guarded REEVALUATION_MARKER / Reevaluation / reevaluate_method() / reevaluate() behind the one new ('rejected','dev-eligible') transition
      npolicy.py            the luck gate's N policy (lab-luck-gate phase 1): POLICIES all-trials / methods / effective, DEFAULT_POLICY, correlation(), participation_ratio(), effective_n() -> NCount. Pure, reads only; `store.gate` is its one caller since lab-luck-gate phase 4
      runner.py             `lab run`: one committed method's variants on the dev window, into the database; git_head(); and the appended test-window half — Tested, resolve_candidate(), preflight_test(), test_trial_row(), run_test() (build-promotion-path phase 4). The luck test's N comes from store.pending_gate since lab-luck-gate phase 4; preflight() refuses a flat-cost variant from M0031 on (real_costs.real_cost_problem, Sean phase 7). Since lab-realistic-gate R2 both halves run on sim.contributions.OWNER_MONTHLY and record a trial_funding row: OWNER_SCHEDULE_TEXT, recorded_contributions(), Ran.funding, trial_rows(deposits=, schedule=). Since eodhd-survivorship-market phase 3 preflight_data() refuses a candidate declaring market_fields = ("series",) on a store with no market series
      prereg.py             the docs/lab/prereg/MNNNN.md pre-registration: Prereg, render()/parse(), require_committed(), check_digest(), check_source(), promote_method() (build-promotion-path phase 3); plus `folds` and `family_state`, the hard gate's record of what the method cleared, tolerated-absent on read so the four committed files still parse (lab-hard-gate phase 2)
      remeasure.py          `lab remeasure`: re-runs a recorded method's variants on the dev window, proves the re-run reproduces each trial's recorded Sharpe and DSR, and appends trial_moments rows -- Batch, Plan, Reproduced, Report, resolve_method(), batches_of(), preflight(), measure(), check(), remeasure(), format_report() (lab-luck-gate phase 3); plus the P7a seed path, resumable and chunk-invariant -- SEED_PREFIX, SEED_METRICS, METRIC_TOL, SeedTrial, SeedPlan, SeedReport, SeedVerdict, is_seed_id(), seed_var_trials(), seed_preflight(), observe(), run_chunk(), reproduce(), remeasure_seed(), seed_verdicts(), format_seed_report() (lab-luck-gate phase 9)
      real_costs.py         `lab costs` (Sean phase 7): REAL_COST_SINCE = 31, requires_real_cost(), real_cost_problem() (the M0031 rule runner.preflight raises); resolve_method(), pick_candidate(), twins(), Side, side_of(), Comparison, measure(), format_report(), insight_text(), journal(). Report only: writes one journal observation, never a trial; since trial-reproducibility the re-run starts at runner.recorded_capital
      name_count.py         `lab names` (GOTRADE_FEE_REBUILD phase 8): NS = (5, 10, 15, 20, 25, 30), ROSTER_NAMES = 20, BASE_VARIANT = "M0007-N20-RAW", MIN_NAMES/MAX_NAMES = 2/60; check_names(), owner_schedule(), check_schedule_support(), variants(), Point, money_weighted(), point_of(), Sweep (of/best/clean/at/agrees), measure(), format_report(), csv_rows(), write_csv(). Sweeps M0007-N20-RAW's `inner.top` at Gotrade's real fees on the owner's contribution schedule, scored money-weighted against a dollar-cost-averaged SPY. Report only, and writes nothing at all: no trial, no moments, no journal entry, no status
      walkforward.py        the lab's own walk-forward (walk-forward-evaluation phases 1-2): MIN_TRAIN_YEARS = 10, EVAL_YEARS = 3, MIN_EVAL_MONTHS = 12, Fold, Slice, FoldPick, folds(), measure(), pick(), evaluate(), Record (scored / won / majority / stable / summary()), BUY_CONDITIONS and buy_signal(). Pure: it slices curves the lab already recorded, runs no backtest and tunes nothing. **Not `backtest/walkforward.py`**, which is P3b's anchored walk-forward for Strategy A2 on the bracket engine
      hardgate.py           the hard gate `lab promote` refuses on (lab-hard-gate phase 1): MIN_FOLDS = 4, COIN_FLIP_NULL, trial_deposits(), Geometry/geometry(), fold_record() -> walkforward.Record, promoted_variant()/variant_record() scoring the variant `lab promote` would pre-register on its own curve (D11), fold_summary(), ingredients() reading `<MNNNN>` allocators out of `trials.config_text` (D12), failed_kin()/family_state() walking `family` ∪ transitive `parent_id` ancestors ∪ ingredients and their family ∪ ancestors, check() raising store.LabError, summary(). SQL plus arithmetic on recorded curves -- no research store, no backtest, no look
      seed.py               one-time import of the pre-lab record (P7a's 54 candidates); since trial-reproducibility writes a source='backfill' trial_provenance row per seed trial
      methods/              one file per method, mNNNN_<slug>.py exporting METHOD
    sean/                   Sean: the owner's real Gotrade orders, marked to market (Sean phases 1 and 4) and replayed against the fee schedule (phase 7)
      __init__.py           docstring only
      ledger.py             pure average-cost ledger (plan contract B), the twin of web/lib/sean/ledger.ts: Order, Holding, Ledger, PnlPoint, build_ledger(), pnl_series(), pnl_at()
      marks.py              daily closes per owner symbol from Yahoo -> sean_marks: yahoo_closes(), fetch_closes() -> Fetched, upsert_marks(), read_marks() (impure)
      equity.py             sean_orders + sean_marks -> sean_equity: read_orders(), symbol_starts(), series(), lock(), replace_equity() (impure)
      calibrate.py          `sean calibrate` (Sean phase 7): every stored receipt against sim.costs -- PaidFees, Residual, Calibration, TOLERANCE, WIB, current_since(), check(), format_report(), wib_date(); pure except rows_from_db()
    commands/
      __init__.py           command-module contract
      migrate.py            `migrate` command
      backfill.py           `backfill` command (phase 3)
      backtest.py           `backtest` command (P3)
      backtest_wf.py        `backtest_wf` command (P3b)
      backtest_b.py         `backtest_b` command (P6a)
      research_store.py     `research_store` command (P7a)
      survivorship_store.py `survivorship_store` command: builds the survivorship-check store engine/.research-sv from the dev store plus the EODHD cache, offline (eodhd-survivorship-market phase 1); since phase 2 --resolve-aliases (offline), --fetch-aliases [--symbols] [--refetch] (network, <cache>/alias/ only), and --build offering accepted alias series by default (--no-aliases)
      market_series.py      `market_series` command: reports, and with --refresh writes, market_series.csv from the EODHD market cache; no network (eodhd-survivorship-market phase 3)
      backtest_dev.py       `backtest_dev` command (P7a)
      lab.py                `lab` command: the method lab (status / luck / show / run / promote / reevaluate / test / remeasure / costs / idea / note / block / unblock / insight / stage / export ...)
      nightly.py            `nightly` command (P1; P4 adds dividends and held paper symbols)
      paper.py              `paper` command (P4)
      paper_check.py        `paper_check` command (P4)
      explain.py            `explain` command (P4; why-this-pick-pipeline phase 3): "Why this pick" notes from stored evidence, every reply vetted by vet()
      veto.py               `veto` command (P6): Strategy C's nightly news check
      promote.py            `promote` command (roster-promotion-pipeline phase 5): a lab method's variant -> a `strategies` row; --lab-override-reason records the admission basis on both sides (lab-luck-gate phase 6)
      compare.py            `compare` command (roster-promotion-pipeline phase 3): read-only ranking over the common window
      sean.py               `sean` command (Sean phase 4): `sean marks` fetches closes for the owner's symbols and rewrites sean_equity; `sean calibrate` (phase 7) checks the fee schedule against every stored order, read-only
  tests/                    pytest; DB tests need PG_TEST_URL
  data/spy_dividends.csv    SPY dividends (ex_date, amount_usd), vendored from yfinance (see data/SOURCES.md)
  data/eodhd_alias_hints.csv hand-checked EODHD codes (symbol,code,note) for members whose history lives under another code; candidates only, read by survivorship_alias (see data/SOURCES.md; eodhd-survivorship-market phase 2)
  .cache/                   gitignored; bars-<max date>-<rows>.pkl and fundamentals-<max filed>-<rows>.pkl written by the backtest loader
  .research/                gitignored; the P7a research store, dev window: bars.csv, dividends.csv, fx.csv, unserved.csv, manifest.json (research_store), plus the optional fundamentals.csv (--with-fundamentals)
  .research-test/           gitignored; the P7b test-window store, the same files (research_store --test-window), its manifest declaring window_name/window_start/window_end; built on the first promotion and never before (build-promotion-path phase 2)
  .research-sv/             gitignored; the survivorship-check store (survivorship_store --build): the dev store's files plus cleaned EODHD members, manifest marked purpose: survivorship-check, plus cleaning_report.csv, coverage_report.txt and (phase 2) alias_report.csv outside the manifest. Vendor rows under a personal licence: never commit
  .cache/eodhd/             gitignored; the EODHD cache (eod/, splits/, dividends/) survivorship_store reads; since phase 2 also alias/ (probe/<CODE>.json per candidate, <SYM>.json per accepted member), the only directory --fetch-aliases writes
docs/backtests/             committed reports: <end>-strategy-a{.md,-equity.csv,-equity.svg} (P3); <end>-strategy-a2-walkforward{.md,-equity.csv,-equity.svg,-variants.svg,-grid.csv} (P3b); <end>-strategy-b-walkforward{.md,-equity.csv,-equity.svg} (P6a); <run date>-p7a-dev-exploration{.md,-rows.csv,-curves.csv,-frontier.svg} (P7a)
docs/plans/                 <run date>-p7b-preregistration.md: the P7b finalists (or "none eligible"), written by backtest_dev (P7a)
docs/lab/prereg/            committed pre-registrations, one MNNNN.md per promoted method, written by `lab promote`; README.md documents the format (build-promotion-path phase 3)
db/migrations/002_engine.sql  (outside the package, owned by it)
db/migrations/003_paper.sql   (outside the package; paper state, book tables, dividends, roster rows; P4)
db/migrations/004_news_veto.sql (outside the package; the C roster row and news_vetoes; P6)
db/migrations/006_roster.sql  (outside the package; the strategies lifecycle and definition columns, and the five seeded rows' definition values; roster-promotion-pipeline phase 1)
db/migrations/007_fnd.sql     (outside the package; the FND roster row, so a database brought up from migrations has one; roster-promotion-pipeline phase 6)
db/migrations/015_sean.sql    (outside the package; Sean's tables: sean_orders, sean_link, sean_reminder_marks, and the engine-written sean_marks and sean_equity)
db/migrations/017_roster_real_fees.sql (outside the package; the six -GT roster rows that pay Gotrade's measured fees, and the thirteen predecessors retired; GOTRADE_FEE_REBUILD phase 12)
```

## CLI

```
python -m seer_engine [--version] [--dry-run] [-v|-vv] <command> [command args]
```

- `--dry-run`: runs every read and every write statement, then rolls back every transaction, so nothing persists.
- `-v`: debug logging. `-vv` also enables debug logging for the `urllib3`, `yfinance` and `peewee` loggers.
- The global flags work on either side of the command name. Documented usage puts them before it.
- Logs go to stderr with UTC ISO timestamps.

**Exit codes** (`cli.main`): 0 success or no-op; 1 an uncaught exception or a failed run; 2
`config.ConfigError` (missing setting) or an unmet precondition returned by a command; 130
Ctrl-C. Otherwise the code is whatever the command's `run()` returns.

### Command contract

Every public module in `seer_engine/commands/` (a name not starting with `_`) is a command:

```python
HELP: str
def add_arguments(p: argparse.ArgumentParser) -> None   # optional
def run(args: argparse.Namespace) -> int               # args.dry_run, args.verbose always set
```

To add a command, add a module. `cli.py` never changes. `discover()` raises `TypeError` if a
module has no callable `run`.

**A literal `%` in a `help=` string must be written `%%`.** argparse runs every `help=` value
through %-interpolation in `HelpFormatter._expand_help`, so `help="... the flat 0.1%, journaled"`
is read as a format spec and the whole `--help` dies with
`ValueError: unsupported format character ','`. `description=` and `epilog=` are **not**
interpolated and must stay single. The failure is as quiet as it is total: a help string is only
expanded when that particular parser's help is rendered, so a bad `%` sits in one subparser doing
nothing until somebody runs `--help` on it — `lab costs` carried one for about a week and `lab
--help` was dead the whole time, with no test, import or lint catching it (lab-realistic-gate R1).
`tests/test_cli.py::test_every_parsers_help_text_formats_without_raising` now walks every parser
reachable from `cli.build_parser()` through the `_SubParsersAction.choices` mapping and calls
`format_help()` on each — the same interpolation `--help` does, without printing or exiting — and
names every parser that raises. It walks rather than listing command names, because a hand-written
list is exactly the thing that goes stale. A one-off AST sweep of every `help=` string under
`engine/src/seer_engine/` at the time found exactly one bad `%`.

### Commands (phase 1)

| Command | Args | What it does |
|---|---|---|
| `migrate` | `--dir PATH` (default `<repo>/db/migrations`) | Applies pending `*.sql` files in file-name order, one transaction per file, and records each in `schema_migrations(name, applied_at)`. It is the twin of `web/scripts/migrate.mjs` and uses the same table and key, so either runner can apply any file. Under `--dry-run`, all pending files are applied in one transaction (later files may depend on earlier ones), which is then rolled back, so not even `schema_migrations` is created. |

### `backfill` (phase 3, P1-ENG-L73U)

```
python -m seer_engine [--dry-run] backfill [--start YYYY-MM-DD] [--end YYYY-MM-DD]
    [--symbols AAPL,BRK.B] [--retry-failed] [--skip-fx | --fx-only] [--batch-size N]
```

A one-off, resumable history load: daily bars from yfinance plus USD/IDR history from Frankfurter.

- **Range**: `--start` defaults to `2015-01-02` (`DEFAULT_START`). `--end` defaults to `dates.last_completed_session(now UTC)`. Both bounds are inclusive. `--start` after `--end` is exit 2.
- **Symbols**: every symbol returned by `universe.all_symbols(conn, since=start)`, which includes SPY. An empty universe (nothing but SPY) is exit 2 with a hint to run `universe refresh` first. `--symbols` takes a comma list in place of the universe and ignores `backfill_log`. Yahoo dash spellings are converted to the dot form.
- **Resume**: by default, symbols already in `backfill_log` with any status (`ok`, `empty` or `failed`) are skipped and counted as "skipped". `--retry-failed` skips only `ok` and re-attempts `failed` and `empty`.
- **Batches**: `--batch-size` symbols per `yf.download` call (default 40, `DEFAULT_BATCH_SIZE`), with a 3 s pause between batches (`BATCH_PAUSE_S`). A rate-limited call is retried after 60, 120 and 240 s (`RATE_LIMIT_BACKOFF_S`). After that, or on any other download exception, the whole batch is logged `failed` and the run continues. A symbol that comes back with no bars in range gets one individual retry, then is logged `empty`.
- **Writes**: each batch's `bars.upsert_bars` and its `backfill_log` upserts run in one `db.transaction`, so a crash loses at most one batch. `backfill_log` stores `status`, `first_date`, `last_date`, `rows` and `error` (cut to 500 characters). The log upsert never downgrades an `ok` row to `failed`, and it skips identical rows.
- **FX**: unless `--skip-fx`, `fx.fetch_range(start, end)` then `fx.upsert_fx` into `fx_rates`, in its own transaction after the bars. An FX fetch failure is reported, and the bars already committed are kept. `--fx-only` skips the bars entirely.
- **Order**: symbol selection (a read), then `demo.purge_demo_if_needed`, then the bars, then FX. No `runs` row is written, and no splits are recorded, because yfinance history is already adjusted for every split up to the moment the backfill runs. Later splits are applied by the nightly command.
- **Idempotent**: every write is an upsert. Re-running with the same arguments changes 0 `bars` and `fx_rates` rows.
- **Output**: a summary on stdout with ok, empty, failed and skipped counts, bar rows fetched and changed, the failed and empty symbol lists, FX rows changed, and the `bars` table size from `pg_total_relation_size`.
- **Exit codes**: 0 when everything succeeded (empty symbols are not a failure); 1 when any symbol failed or the FX fetch failed; 2 for a bad range or an empty universe (`BackfillError`).
- **Testing seams**: `backfill(conn, opts, *, downloader=None, sleep=time.sleep, fetch_fx=None) -> Summary` takes injectable network and sleep callables. `fetch_batch`, `select_symbols`, `options_from_args` and `format_summary` are also public.

### `backtest` (P3)

```
SEER_ENV_FILE=/path/to/.env.local python -m seer_engine backtest [--out DIR] [--cache-dir DIR]
    [--refresh-cache] [--is-start YYYY-MM-DD] [--oos-start YYYY-MM-DD] [--end YYYY-MM-DD] [--dividends PATH]
```

Runs Strategy A's 10-year backtest against Neon and writes the report. **Read-only**: it reads
`bars`, `universe` and `fx_rates` and writes nothing to any table; `--dry-run` changes nothing.

- **Defaults are the committed run.** `--out` defaults to `<repo>/docs/backtests`, the windows to
  `tuning.IS_START` / `tuning.OOS_START` / the last SPY bar, `--dividends` to
  `engine/data/spy_dividends.csv`. The window flags exist for synthetic tests; passing them for a
  real run is how out-of-sample tuning starts, so don't.
- **Steps:** load the market (cached), `STRATEGY_A.prepare` once, the 81 in-sample grid runs,
  `select` on in-sample metrics only, then one out-of-sample run and one full-window run with the
  selection, both SPY curves per window, the survivorship count, the gate, and the three files.
- **Cache:** bars are read with one streamed `COPY ... TO STDOUT` and pickled to
  `<cache dir>/bars-<max date>-<rows>.pkl`; `--cache-dir` defaults to `engine/.cache` (gitignored)
  and exists so tests keep the cache out of the repo. Each run first asks Neon for
  `max(date), count(*)` from `bars`; a different fingerprint reloads. `--refresh-cache` forces a
  reload. `universe` and `fx_rates` are small and read every time.
- **Output:** `<out>/<data end>-strategy-a.md`, `-equity.csv`, `-equity.svg`. The stem uses the
  data end date, so a re-run on the same data overwrites the same files byte-identically.
- **Logs:** cache hit or miss, wall time per grid run and in total, the selection, the gate verdict.
- **Exit codes:** 0 whether the gate passes or fails (a losing verdict is a result); 1 on an error;
  2 on a precondition (no bars, no SPY bars, a window date that is not an NYSE session or is after
  the last SPY bar, `is_start < oos_start <= end` violated, no FX row on or before `--is-start`, a
  missing dividends file).
- **Worktrees:** `config.REPO_ROOT` is the worktree, which has no `.env.local`, so set
  `SEER_ENV_FILE` to the main checkout's file. Never `source` it.

### `backtest_wf` (P3b)

```
SEER_ENV_FILE=/path/to/.env.local python -m seer_engine backtest_wf [--dry-run] [-v] [--out DIR] [--cache-dir DIR]
    [--refresh-cache] [--is-start YYYY-MM-DD] [--first-year YYYY] [--end YYYY-MM-DD] [--dividends PATH]
```

This runs Strategy A2's anchored yearly walk-forward against Neon and writes the P3b report.
Command names are module names, and a hyphen is not legal in one, hence the underscore.
**Read-only**, like `backtest`: it reads `bars`, `universe` and `fx_rates` and writes nothing to
any table, `strategies.params` included. `--dry-run` changes nothing (there are no DB writes to roll
back); the report files are still written.

- **Defaults are the committed run.**
  - `--out` defaults to `<repo>/docs/backtests`, `--is-start` to `tuning.IS_START` (2015-10-19),
    `--first-year` to `walkforward.FIRST_TRADE_YEAR` (2018), `--end` to the last SPY bar, and
    `--dividends` to `engine/data/spy_dividends.csv`.
  - The window flags exist for synthetic tests. Passing them for a real run is how tuning on traded
    data starts, so don't.
- **Steps:**
  1. Load the market (the same bar cache as `backtest`).
  2. `STRATEGY_A2.prepare` once, then the folds.
  3. Tuning: one run per each of the 324 (variant × grid) combinations over 2015-10-19 → the last
     fold's tune end, sliced per fold with `metrics_through`.
  4. The combined selection per fold, and each variant's own.
  5. Five walk-forward runs (combined + 4 variants), each one continuous portfolio from 2018-01-02.
  6. Both SPY curves from the same starting cash, survivorship, `gate_p3b`, and the five files.
- **Output:** `<out>/<data end>-strategy-a2-walkforward.md`, `-equity.csv`, `-equity.svg`,
  `-variants.svg`, `-grid.csv`. A re-run on the same data overwrites them byte-identically.
- **Logs:**
  - cache hit or miss;
  - the prepare time;
  - wall time per combination and in total;
  - every fold's selection;
  - the gate verdict;
  - whether `STRATEGY_A2_PARAMS` equals the last fold's selection.
- **Exit codes:**
  - 0 whether the gate passes or fails, because a losing verdict is a result.
  - 1 on an error.
  - 2 on a precondition, as for `backtest`: no bars, no SPY bars, a window date that is not an NYSE
    session or is after the last SPY bar, no fold to trade, no FX row on or before `--is-start`, or
    a missing dividends file.
- **Worktrees:** as for `backtest`, set `SEER_ENV_FILE` to the main checkout's `.env.local`. Never
  `source` it.
- **One round.** The committed run is P3b's single rework of Strategy A. Re-running it on newer data
  re-measures the same pre-registered procedure. Adding a variant or a grid value after seeing
  results is not allowed.

### `backtest_b` (P6a)

```
SEER_ENV_FILE=/path/to/.env.local python -m seer_engine backtest_b [--dry-run] [-v] [--out DIR] [--cache-dir DIR]
    [--refresh-cache] [--is-start YYYY-MM-DD] [--first-year YYYY] [--end YYYY-MM-DD] [--dividends PATH]
    [--model-dir DIR]
```

This runs Strategy B's anchored yearly walk-forward against Neon and writes the P6a report.
**Read-only**, like `backtest_wf`: it reads `bars`, `universe` and `fx_rates`, and writes nothing to
any table, `strategies.params` included. `--dry-run` changes nothing: the report files (and a
passing run's artifact) are written as usual.

- **Defaults are the committed run.**
  - `--out` defaults to `<repo>/docs/backtests`, `--cache-dir` to `engine/.cache` (shared with
    `backtest` and `backtest_wf`) and `--model-dir` to `<repo>/engine/data/models`.
  - The window flags have `backtest_wf`'s defaults (2015-10-19, 2018, the last SPY bar, and
    `engine/data/spy_dividends.csv`). They exist for synthetic tests. Passing them for a real run
    is how training on traded data starts, so don't.
- **Steps:**
  1. Load the market, from the same bar cache as `backtest`.
  2. The folds; `prepare_b` once; the candidate table with its labels.
  3. Per fold, a tree fit and a ridge fit on the purged rows, sequential, in fold order. Then the
     determinism probe on the last fold, which decides the gated curve.
  4. The B and B-linear walk-forward runs, each one continuous portfolio from 2018-01-02.
  5. A2's combined walk-forward, recomputed through `backtest_wf`'s `tune_all` + `run_walk_forward`
     as information.
  6. Both SPY curves, survivorship, passed nights, calibration, `gate_p6a`, and the three files.
  7. On a pass, the gated curve's last-fold model goes to `<model-dir>/<data end>-strategy-b.pkl`,
     and its sha256 is logged with the instruction to freeze it.
- **Output:** `<out>/<data end>-strategy-b-walkforward.md`, `-equity.csv` and `-equity.svg`, plus
  the artifact on a pass. A re-run on the same data overwrites them byte-identically. Only the
  `frozen-model:` line, and what renders from it, follows `STRATEGY_B_FROZEN`.
- **Logs:** cache hit or miss, the wall time of every step, every fold's training summary, the
  probe result, the gate verdict, and the artifact path and sha256 on a pass. Wall times appear in
  logs only, never in a file.
- **Exit codes:**
  - 0 whether the gate passes or fails, because a losing verdict is a result.
  - 1 on an error.
  - 2 on a precondition, the same ones as `backtest_wf` (`backtest_wf.resolve`: no bars, no SPY
    bars, a window date that is not an NYSE session or is after the last SPY bar, no fold to trade,
    no FX row on or before `--is-start`), or a missing dividends file.
- **Worktrees:** as for `backtest`, set `SEER_ENV_FILE` to the main checkout's `.env.local`. Never
  `source` it.
- **One round.** The committed run is B's single round on this data. Re-running it on newer data
  re-measures the same pre-registered procedure. Changing a feature, the label, a hyperparameter or
  the pick rule after seeing results is not allowed.

### `research_store` (P7a)

```
python -m seer_engine research_store [--dry-run] [-v] [--store STORE] [--batch-size BATCH_SIZE] [--verify]
                                    [--with-fundamentals] [--refresh-fundamentals] [--coverage]
                                    [--test-window [--window-end YYYY-MM-DD]]
```

This builds the local research store (D5). It covers bars for every S&P 500 member since 1996 and
Nasdaq-100 member since 2007 that yfinance can serve, plus the 21 research ETFs, cash dividends
from the start, and Frankfurter USD/IDR. It **never connects to Neon** and needs no database
setting — `--with-fundamentals` is the single exception, below.

**Two windows, two stores** (build-promotion-path phase 2): the **dev window**
(1993-01-29..2015-10-16) in `engine/.research` is the default — what `lab run` and `backtest_dev`
read, and the store whose fingerprint every recorded lab trial was measured against — and the
**test window** (2015-10-19..data end) lives in `engine/.research-test` behind `--test-window`,
read only by `lab test`. The two are **not** interchangeable: `research.load_store` refuses a store
whose declared window is not the one the caller asked for, and this command refuses (exit 2) to
build one window into the other's directory even when the operator names it explicitly — by **path**
for this checkout's own two directories, and, since research-store-clobber-guard, by **content** as
well: a build reads the target's own `manifest.json` (`research.declared_window`) and refuses when
the store already sitting there declares the other window, which protects a store in **any** checkout
or worktree and not merely the running one. A target holding no readable store declares nothing, so
the first build of all still proceeds.

- **`--store`** defaults to `engine/.research` (gitignored), or `engine/.research-test` with
  `--test-window`, and **`--batch-size`** to 40 symbols per yfinance request.
- **`--test-window`** (build-promotion-path phase 2) acts on the P7b test store. A build covers
  `2015-10-19..`the latest completed NYSE session and records that window in the manifest's three
  optional keys. It still holds the **same deep history from 1993-01-29** as the dev store — a
  candidate first traded on 2015-10-19 needs its `lookback` bars before that date, and the one
  look per configuration is append-only, so a store starting at its own window start would make
  that look permanently wrong. The universe follows the window at both ends, so every company that
  joined the index after October 2015 is in and everything that left before 2015-10-19 is out.
  Build it only when something is being promoted (design S3), never speculatively.
- **`--window-end`** pins the test window's last scored session instead of taking the latest
  completed one, so an interrupted build can be resumed to the *same* end rather than silently
  moving. It must be an NYSE session after `DEV_END`, applies only with `--test-window`, and only
  to a build — `--verify`, `--coverage` and `--refresh-fundamentals` read the window the store
  already declares (exit 2 otherwise).
- **`--with-fundamentals`** (edgar-fundamentals) additionally reads the SEC point-in-time fact
  panel through `backtest.io.read_facts()` (`DATABASE_URL_UNPOOLED`, the one place in this command
  that needs a database) and writes it as the store's **optional** fifth file, `fundamentals.csv`,
  so a later dev/lab run sees a non-empty `Market.fundamentals`. Without the flag the store carries
  no panel and the run ranks on bars alone, silently. The read lives in `backtest/io.py`, not here:
  `test_research_store.py::test_no_neon_and_no_database_url_needed` AST-scans both `research.py`
  and this command and fails either one that names `seer_engine.db` or `psycopg`. Omitting the flag
  leaves the store byte-identical to a pre-fundamentals build, fingerprint included.
- **`--refresh-fundamentals`** (fundamental-panel-coverage) rewrites `fundamentals.csv` **only**:
  `bars.csv`, `dividends.csv`, `fx.csv` and `unserved.csv` are carried over from the existing
  store byte for byte and every `_COUNT_KEYS` value with them, so the panel changes and the bar
  history does not. It exists because `build_store` always downloads every symbol's bars first,
  and two yfinance crawls on two days give two different fingerprints — which would break
  comparability with the trials already recorded. It needs `DATABASE_URL_UNPOOLED` (set
  `SEER_ENV_FILE` to the train env file) and re-seals and swaps atomically; nothing is written
  on failure. Re-sealing **re-declares the window the store already had**, so refreshing a store
  can never change which window it is for, and the mode refuses a store whose declared window
  disagrees with `--test-window`.
- **`--coverage`** (fundamental-panel-coverage) loads the store and prints, for each sampled
  dev-window date, how many symbols the panel can actually rank — a symbol counts only when
  `as_of` returns a snapshot with **non-empty `observations`** whose newest fact was filed within
  `max_stale_days` — plus one fraction over the window. `as_of` never returns `None`, so a
  presence check measures nothing; this is the content check, and it is the same measure
  `lab run` refuses on below `fundamentals.coverage.MIN_DEV_COVERAGE`. No network, no database.
  It reads no bars, so membership, `min_price` and `min_dollar_volume` are not applied and the
  fraction is an **upper bound**: below the floor is conclusive, above it is necessary and not
  sufficient. It is a **dev-window** measure and is refused (exit 2) with `--test-window`.
- **The build** is throttled with backoff and runs all-or-nothing: temp files first, then a rename.
  The same downloads give byte-identical files and the same fingerprint. Nothing dated after the
  window's end is kept — 2015-10-16 on the dev window, the recorded `window_end` on a test store.
- **`--verify`** uses no network. It loads the store, checks every file's sha256 against
  `manifest.json` and that no row is after the store's declared window end, runs three data checks
  (SPY has a bar on every NYSE session from 1993-02-01 through that end; SPY's dividends equal the
  vendored `data/spy_dividends.csv` on the overlap of the two; AAPL's 2012 dividends are on the
  split-adjusted price scale), and prints the window, the fingerprint and the counts. The printed
  window states what is **scored** and `store_start` what is **held**, which differ on a test
  store. It is the check to run before any dev run, and it refuses a store whose declared window
  disagrees with `--test-window`.
- **`--dry-run`** builds into a temporary directory, verifies it, and discards it.
- **Logs:** batches, unserved symbols, counts, and the fingerprint.
- **Exit codes:** 0 when the store is built (or loaded) and all three checks pass; 1 when the build
  fails (nothing is written, any previous store is kept) or a check fails; 2 when the store is
  missing or invalid (a tampered file, or a row after the declared window's end), or when the flags
  refuse — a store/window mismatch, `--test-window` aimed at `engine/.research` or a dev invocation
  aimed at `engine/.research-test`, a **build** whose target directory already holds a store whose
  manifest declares the other window (the content guard, which holds wherever that store lives),
  `--window-end` without `--test-window` or on a read-only mode, or `--coverage` with
  `--test-window`.

### `survivorship_store` (eodhd-survivorship-market phase 1, P1-ENG-8X1K)

```
python -m seer_engine survivorship_store [--build | --report] [--out DIR] [--source DIR] [--cache DIR] [--no-aliases]
python -m seer_engine survivorship_store --resolve-aliases [--symbols A,B]
python -m seer_engine survivorship_store --fetch-aliases [--symbols A,B] [--refetch]
```

Builds the **survivorship-check store**: a dev-window store that answers how much the dev store's
missing delisted companies flatter a recorded result. **No network, no Neon**: it reads the dev
store and the local EODHD cache only.

- **No flag** cleans every cached series and prints the coverage report; it writes nothing.
  **`--build`** writes the store at `--out`; **`--report`** prints the two reports of the store
  already there.
- **`--out`** defaults to `research.SV_STORE_DIR` (`engine/.research-sv`, gitignored). It must not
  be the source, a symlink, or the dev or test store's directory. **`--source`** defaults to the dev
  store (`engine/.research`), read only and verified with `research.load_store` first; a source that
  is itself a survivorship-check store is refused. **`--cache`** defaults to `engine/.cache/eodhd`
  (`eod/`, `splits/`, `dividends/`).
- **What it writes**, built in `<out>.tmp` and swapped in whole: `bars.csv` / `dividends.csv` with
  the source's lines byte for byte and the added symbols' lines at their sorted place; `fx.csv` and
  every optional file copied and sha-checked; `unserved.csv` (members still without a bar, with the
  cleaning's reason); `dividend_announcements.csv` re-matched over the merged dividends; and a
  manifest sealed for the dev window with `"purpose": "survivorship-check"`, so its **price
  fingerprint is its own**. The built store is loaded once more before the swap. The dev store is
  never written and stays byte-identical.
- **Reports, inside the store but outside the manifest** (the loader ignores unlisted files, so they
  never touch the fingerprint): `cleaning_report.csv`, one row per cached symbol the dev store
  could not serve, with its action (`kept` / `repaired` / `trimmed` / `dropped`), reason and counts;
  and `coverage_report.txt`, member-days per year before and after, plus the members still missing.
- **Measured on the real cache** (2026-10-10): member-day coverage 58.6% -> 81.3%; 187 kept,
  73 repaired, 62 trimmed, 200 dropped; 239 members still missing.
- **Alias fill** (phase 2, P1-ENG-SLCU; see `survivorship_alias` under Exported API). For the
  members whose cached series is unusable under their store symbol:
  - **`--resolve-aliases`** is offline: per member, the candidate codes, which one fits, and why.
  - **`--fetch-aliases`** is the command's **only network path** (`EODHD_API_TOKEN`; in a worktree
    via `SEER_ENV_FILE`). Resumable: codes already probed are skipped unless **`--refetch`**. It
    writes under `<cache>/alias/` only (`probe/<CODE>.json`, `<SYM>.json`); `eod/`, `splits/` and
    `dividends/` are only read. The global `--dry-run` fetches and writes nothing.
  - **`--symbols A,B`** limits either mode to those members; one that already has a usable series
    is refused.
  - **`--build`** (and the no-flag report) offers the accepted alias series to `plan_build` as
    `extra_sources` by default, re-resolved from the cached probes so only a code that is still the
    resolver's choice is used; each is cleaned like any other series and `best_of` keeps whichever
    covers more member days. It writes **`alias_report.csv`** beside the other reports (outside the
    manifest), and an alias-filled symbol carries source `eodhd-alias` in `cleaning_report.csv`.
    **`--no-aliases`** gives phase 1's build alone; a cache without EODHD's symbol lists skips the
    fill with a warning.
  - **Measured** (2026-10-10): 128 of 200 filled; member-day coverage 81.3% -> 89.0%; members still
    missing 239 -> 111; SV price fingerprint `60adae1b…` (was `bc5ba895…`).
- **The store is report-only.** `lab run`, `lab test` and `lab remeasure` refuse it (exit 2) before
  any trial row is written; see `research.PURPOSE_KEY` under Exported API.
- **Exit codes:** 0 ok; 2 refused (paths, a source that does not verify or is itself a
  survivorship-check store, or, for `--report`, a store at `--out` that is not one; for the alias
  modes, no token, a missing input, or a `--symbols` member that already has a usable series);
  1 when `--fetch-aliases` failed for some members (the rest are cached).
- Tests: `tests/test_survivorship_store.py` (37), `tests/test_survivorship_alias.py` (22).

### `market_series` (eodhd-survivorship-market phase 3, P1-ENG-9L1M)

```
python -m seer_engine [--dry-run] market_series [--refresh] [--store DIR] [--cache DIR]
```

Reports the market-wide daily series cached from EODHD and, with `--refresh`, writes them into a
research store as `market_series.csv`. **Cache only**: it reads `engine/.cache/eodhd/market/<TICKER>.json`
(gitignored; the licence is personal, so raw rows never enter git or `web/`), needs no token and
never fetches a missing file.

- **Sources** (`SOURCES`, in `research.MARKET_SERIES_NAMES` order, pinned equal by a test):
  `VIX`, `VIX9D`, `VXN`, `VVIX` the close in index points; `VIX3M` from `VIX3M.INDX` wherever it
  has a close, else `VXV.INDX` (its name until 2007-11-13); `T13W` the `IRX.INDX` close, already
  a yield in percent; `T5Y` / `T10Y` / `T30Y` the `FVX` / `TNX` / `TYX` close **divided by 10**
  (TNX 65.48 on 2000-01-03 is a 6.548% ten-year yield); `GOLD` the `XAUUSD.FOREX` close in USD/oz.
- **Rows dropped and counted**: dated before `research.STORE_START` or after the store's window
  end, on a day that was not an NYSE session (bond and FX markets publish on some stock-market
  holidays), or with no close.
- **The report** prints one coverage row per series (unit, rows, first/last date, member-day
  share, off-session / outside / no-close counts, rows per source ticker) and, for a spliced
  series, how often the two tickers agree on the sessions both have.
- **`--store`** defaults to `research.STORE_DIR`; the window is the one the store declares
  (`research.declared_window`). **`--refresh`** writes through `research.refresh_market_series`:
  every other store file is carried over byte for byte and the directory is swapped in whole, so
  the **price fingerprint does not move** — the command prints both fingerprints and exits 2 if
  the price fingerprint changed. The global `--dry-run` prints what it would write and writes
  nothing.
- **Exit codes:** 0 ok; 2 the store's manifest is missing or unreadable, a cache file is missing
  or unreadable, a series has no row in the window (on `--refresh`), or the refresh was refused.
- A full `build_store` does not write the file; re-run `market_series --refresh` after a rebuild.
- Tests: `tests/test_market_series.py` (49 collected).

### `backtest_dev` (P7a)

```
python -m seer_engine backtest_dev [--dry-run] [-v] [--store DIR] [--out DIR] [--plans DIR] [--run-date YYYY-MM-DD] [--only ID [ID ...]]
```

This runs every candidate in `backtest/registry.py` on the **development window only** (each
candidate's own start → 2015-10-16) and writes the P7a report set and the P7b pre-registration. It
reads only the research store. **No Neon, no network.**

- **Defaults are the committed run:** `--store engine/.research`, `--out docs/backtests` and
  `--plans docs/plans`. `--run-date` defaults to today, and it appears in file names only.
- **No `--end` exists.** Every entry point rejects a session after 2015-10-16 (`DevWindowError`),
  and the store holds no later row (D9).
- **Pre-registration guard:** the command exits 2 while `backtest/registry.py` has uncommitted
  changes (or is untracked), so every committed report comes from a committed registry (D6).
  `--only ID ...` skips the guard for smoke runs: it runs those candidates in registry order,
  renders the files in memory, logs an estimate of the full run's time, and **writes nothing**.
- **`--dry-run`** changes nothing: the command never touches the database, and a full run still
  writes its report files.
- **Steps:**
  1. Load and verify the store.
  2. Run every candidate, sequentially, in registry order.
  3. Compute D8 and the deflated Sharpe.
  4. Render all five files, then write them.
- **Output:** `<out>/<run date>-p7a-dev-exploration.md`, `-rows.csv`, `-curves.csv` and
  `-frontier.svg`, plus `<plans>/<run date>-p7b-preregistration.md`. A re-run with the same
  `--run-date` overwrites them byte-identically.
- **Logs:** the store fingerprint, one line per candidate (its result, failed D8 conditions and
  wall time), and the finalist ids or "none eligible". Wall times appear in logs only, never in a
  file.
- **Exit codes:**
  - 0 whether or not any candidate is eligible, because "none eligible" is a result.
  - 1 on an error.
  - 2 on a precondition: a dirty registry, an unknown `--only` id, a missing or invalid store, or
    `research.DEV_END` differing from `backtest.dev.DEV_END`.
- **One run per registry state.** Appending a candidate (D6) means a new commit before its run, and
  every try is reported.

### `paper` (P4)

```
usage: seer_engine paper [-h] [--dry-run] [-v] [--now ISO8601]
```

The nightly paper step for the frozen roster (`docs/runbooks/paper-trading.md`).

- **Precondition**: the real `runs` row for `run_dates(now).session_date` has `status = success`. Otherwise nothing is written and it exits 1 (design §8: a failed bars run means no paper step).
- **The roster comes from the database** (phase 2): `store.read_roster_rows` through `roster.from_rows`, not the compiled `ROSTER`. A row whose `object_name` or `rules_id` cannot be resolved stops the night by name and writes nothing — never a silently dropped portfolio. An entry on the roster with no `paper_start` starts tonight, exactly as any new entry does.
- **`FND`** (phase 6) is on the roster like any other row and starts on its next night, with no `paper_start` written by migration 007 and no special case in the command. It is the roster's one `MarketAware` object: `paper.book.decide_book` prepares it from the whole `Market` so it ranks on `market.fundamentals`. On a database without `005_fundamentals.sql` applied — or with the table empty — the panel is `EMPTY_PANEL`, no symbol is eligible and FND holds cash: an all-cash FND, never a wrong one.
- **The rebuilt roster** (GOTRADE_FEE_REBUILD phase 12, migration 017): the six entries that trade are `SPY-GT`, `C-GT`, `RMW-FR-GT`, `RAW-FR-GT`, `MOM-FR-GT` and `MVW-FR-GT`, each paying Gotrade's measured fee schedule (`sim/costs.py`) instead of the assumed flat 0.1% a side. They are **new ids with fresh paper clocks**, not edits: `cost_model` is in `sim.rules.LEVERS_SINCE_PINS`, so moving a started entry onto `"gotrade"` would move its spec digest and `store.check_digest` would refuse its next night. The six predecessors (`SPY`, `C`, `RMW-FR`, `RAW-FR`, `MOM-FR`, `MVW-FR`) are **retired, never deleted** — every row they wrote, their specs and their un-stepped 2026-10-07 decisions stay. It cost nothing: zero sessions had ever been stepped. **Paper is still paused** (`nightly.yml`'s `PAPER_PAUSED: 'true'`): 017 applies on the next nightly and the rebuilt roster sits inert — no `paper_start` written, no session stepped — until the owner flips the switch himself.
- **Each entry trades under its own rule set**: `settle_bracket`, `decide_bracket` and `repick` are all handed `rules=e.rules`, so `C` is decided at `DESIGN_V0` and `C-GT` at the Gotrade bracket preset (`design-v0-gotrade`). No module constant stands in for the entry's own rules anywhere on the night.
- **The benchmark's cost model is the roster's statement about that entry**: `_step_benchmark` calls `store.load_benchmark(conn, e.id, cost_model=roster.benchmark_cost_model(e.id))`, never a module default. `SPY` was started flat and keeps flat; `SPY-GT` pays Gotrade's schedule. The frozen spec records the same value, so what is pinned and what is charged are one statement.
- **The owner's contributions** (10,000,000 IDR to start, +5,000,000 IDR on the 25th of each month): once per entry per night, before anything steps, `_trade` calls `store.accrue_contributions(conn, e.id, OWNER_MONTHLY.dates_in(paper_start, sessions[-1]), OWNER_MONTHLY.amount_idr, through=sessions[-1], usd_idr_on=…)`, which freezes each deposit at the USD/IDR of its own landing session and leaves an already-recorded one alone — so a backfilled `fx_rates` can never move a stepped book's history. Each session loop then credits what has landed with `store.apply_contributions(conn, e.id, s)`: a book through `paper.book.deposit_book`, a bracket by adding to **both `cash` and `equity`** (sizing reads the last snapshot's equity, so cash alone would leave the book permanently under-deployed), and the benchmark through `step_benchmark(..., deposit=…)`, which spends it at that close like `buy_and_hold` does rather than banking it. The yardstick is fed the same money on the same dates as the books it is measured against.
- **First night**: writes each roster row's frozen spec (`params`) and `paper_start = session_date`, `paper_state` (initial cash `paper.capital.PAPER_INITIAL_IDR`, 10,000,000 IDR, at the latest FX on or before `data_date`), day-0 snapshots at `data_date`, and the first decisions.
- **Every night**: steps every session after `paper_state.last_session` through `data_date` for every strategy, then decides `session_date`. See Usage, "Paper: one night".
- **Retired entries** (`status = 'retired'`) take no decision at all: no orders, no equity snapshot, no `paper_state` step, and no history row is read or written. The only column the night may write for one is `paper_end`, stamped with the last session it actually traded and only when a retirement taken by hand SQL left it NULL. Once every retirement is stamped the night is an ordinary no-op again, so an all-retired roster is cheap rather than a crash. A `status` the night does not understand fails it instead of guessing, and a deliberate skip never shares a code path or a log line with an unresolvable row.
- **Split-cadence books** (paper split cadence, phase 2; rules with a `resize_cadence`, e.g. `monthly-rank-weekly-resize-frac`: pick monthly, resize weekly): `_start` and `_step_book` hand `decide_book` the last rank's basket, read back from that rank session's `book_targets` rows on tonight's own connection (`paper.book.last_rank_session`, then `rank_basket` drops the idle row; no migration), so a rank decided earlier in a catch-up loop is seen, plus `marks` from the settled book. The basket is never recomputed on a resize-only night, and a resize-only decision opens no position, so it stores no evidence. A rule set without `resize_cadence` takes none of these reads and calls `decide_book` exactly as before. `tests/test_paper_split_cadence.py` (Postgres) pins it: 20 nights equal `run_rules`, catch-up across a monthly rank, a 2:1 split on a held symbol (`paper_check` says `split-affected`, never a mismatch), a stopped-out position not re-bought, and a `promote --fractional` split-cadence candidate trading to a green `paper_check`.
- **Strategy C**: C's strategy object is given the verdicts stored in `news_vetoes` for the sessions being decided (`store.allowed_between`); only `allow` is bought, and a missing verdict counts as `failed`. `paper` makes no network call and never fails because of C's verdicts.
- **Idempotent** per (strategy, session): a re-run for a session already done writes nothing.
- **One transaction** for the whole night plus `runs.paper_status`. A failure rolls back everything and records `paper_status = failed`.
- **Frozen spec**: a started strategy whose stored digest differs from `paper/roster.py` fails the night as `store.SpecMismatch` (rolled back, `paper_status = failed`, exit 1). A `paper_start` with no `paper_state` is refused the same way until the clock is reset.
- **Exit codes**: 0 = stepped and decided, or already done (no-op); 1 = no successful bars run for the session (nothing written), or the night failed (rolled back, `paper_status = failed`, `paper_error` set); 2 = missing setting (`DATABASE_URL_UNPOOLED`).

### `paper_check` (P4)

```
usage: seer_engine paper_check [-h] [--dry-run] [-v] [--require-sessions N]
```

The read-only replay check (D7). See Usage, "Paper: replay check". The roster is read from the `strategies` rows in the same read-only transaction (phase 2), so the replay checks exactly what the night traded; a retired strategy is replayed like any other, keeping its `paper_start`, its `paper_state` and every history row. C is replayed from its stored verdicts, read in the same read-only transaction; the LLM is never asked again. A bracket entry is replayed under **its own** `rules` (`DESIGN_V0` for `C`, the Gotrade bracket preset for `C-GT`), so a Gotrade entry is never reconstructed at the flat rate. The owner's deposits go in as the **record**, never the schedule (`_deposits`: the `applied` `paper_contributions` rows as `(session, usd)` pairs, ascending): each amount was frozen at the rate of the day it landed, so re-deriving it from `OWNER_MONTHLY` would disagree with the stored record the first time the rupiah moved. The stored records also publish `deposited` — the dollars credited since day 0 — **beside** `initial_cash` rather than folded into it, because once deposits exist "capital on day 0" and "capital in" are different numbers. "Not started" (no `paper_start`) is a pass. A strategy touched by an applied split is reported `split-affected`, not failed. `--require-sessions N` is the v0.1.0 release check. Exit codes: 0 = every started strategy `ok` or `split-affected` (or none started); 1 = a mismatch, or `--require-sessions N` unmet (`not-started` counts as 0); 2 = missing setting.

### `explain` (P4)

```
usage: seer_engine explain [-h] [--dry-run] [-v]
```

"Why this pick" notes (D9) for new paper entries without one: `orders.explanation` for A's and C's new pending orders, `book_targets.explanation` for new (not already held) targets of the latest decision. The prompt is the entry's stored `evidence` (migration 009) and the method's plain name (`plain_name("F4 · Momentum") == "Momentum"`), nothing else. An entry with NULL or empty evidence is skipped. The call is `complete(SYSTEM, prompt, temperature=0.0, thinking="disabled", max_tokens=EXPLAIN_MAX_TOKENS)` (1024). Every reply passes `vet(reply, facts, earlier)` or is discarded (logged with the reason, text stays NULL): `clean` (markdown, bullet and wrapping quotes removed, whitespace collapsed, never cut), ends with `.`/`!`/`?`, no ellipsis, at most `MAX_SENTENCES = 2` sentences and `MAX_CHARS = 320` characters, no `BANNED` phrase (advice or prediction, word-bounded), every `numbers_in(text)` within `numbers_in(facts)` (normalized: `$ , % +` dropped, trailing zeros removed; ticker digits are not numbers), and not equal (case-folded) to a note already accepted for the same strategy tonight. `accept(...)` is the same check returning `str | None`. Only calls that raise count toward `MAX_CONSECUTIVE_FAILURES = 3`; a rejection resets the count. Missing or empty `LLM_*` settings leave every text NULL and exit 0. Paper correctness never depends on it. Exit 1 only on a database error; 2 when `LLM_*` is set but `DATABASE_URL_UNPOOLED` is missing.

### `veto` (P6, Strategy C)

```
usage: seer_engine veto [-h] [--dry-run] [-v] [--now ISO8601]
```

Strategy C's nightly news check (handover D6; `docs/runbooks/paper-trading.md`, "Strategy C: the news check"). The nightly job runs it after `nightly` and before `paper`, as a `continue-on-error` step with a 10-minute limit. It runs outside `paper`'s transaction, so `paper` stays one network-free transaction.

- **Clock**: `started_at = now` (tz-aware UTC; `--now` for tests) is both the news cutoff and every row's `decided_at`. `rd = dates.run_dates(now)`; the session checked is `rd.session_date`.
- **Precondition**: the real `runs` row for that session has `status = success`. Otherwise exit 1, nothing written, no network call.
- **Nothing to do**: C already has rows for the session (`store.has_vetoes`): "already checked", exit 0, no Finnhub or LLM call. `paper` has already decided the session: "too late", exit 0, nothing written.
- **Candidates**: `strategies.c.candidates` on `store.load_market_window(conn, store.market_window_since(rd.data_date))` at `rd.data_date` (A's ranked picks, the first 10), read and rolled back before any network call. None: exit 0, nothing written.
- **Per candidate**, in rank order: `finnhub.Client.company_news(symbol, *news_dates(started_at, 3))` → `select_headlines(..., cutoff=started_at, cap=20)`; `finnhub.Client.earnings(symbol, *earnings_window(session, 5))`; `llm.Client(cfg, timeout=30.0, retries=1).complete(SYSTEM_PROMPT, user_prompt(...), temperature=float(params.temperature), thinking=params.thinking, max_tokens=params.max_tokens)` (0.0, "disabled", 1024, all from C's frozen `CParams`) → `parse_verdict`.
- **A failure is a verdict, never an exception**: `failed`, with a plain reason redacted and cut to 300 characters, when `FINNHUB_API_KEY` is unset, any `LLM_*` is unset, `LLM_MODEL` is not C's frozen model ("LLM_MODEL <x> is not C's frozen model glm-5.3"), Finnhub or the LLM errors, the reply is unparsable, or `MAX_CONSECUTIVE_FAILURES = 3` network failures in a row stopped the rest ("skipped after 3 consecutive failures").
- **One write**: one transaction re-checks `has_vetoes` (another run may have won) and writes every row with `store.write_vetoes`. `--dry-run` makes the real calls, then rolls back. No secret reaches a row or a log line.
- **Exit codes**: 0 = rows written (whatever the verdicts, all `failed` included), nothing to do, or no candidates; 1 = no successful bars run for the session, or a database error; 2 = missing setting (`DATABASE_URL_UNPOOLED`).

### `promote` (roster-promotion-pipeline phase 5, P1-ENG-Z8MR)

```
usage: seer_engine promote [-h] [--dry-run] [-v] --method M0001 [--candidate M0001-A]
                           --id FND --name NAME --sub SUB [--icon ICON] [--sort N]
                           --gate-note NOTE [--gate-not-applicable] [--retire ID]
                           [--lab-db PATH] [--lab-status-stays]
                           [--lab-override-reason REASON]
```

The lab → roster bridge (plan Decisions D1, D3, D5, D6): it puts a lab method's pre-registered variant on the paper roster as a `strategies` row. It is the only writer that creates a roster entry, it is run by hand, and the nightly job never calls it.

- **Promotable means three things**, and anything that is not all three is refused. (1) The method file exposes the variant as a `Candidate` — a frozen (rules, allocator, params) triple; the roster entry is that triple unchanged, and nothing here invents a parameter. (2) The variant's allocator is a value `paper.roster.RESOLVER` names: `object_name_of(obj)` inverts `RESOLVER`, and raises `NotPromotable` both when no name maps to the object (the message gives the `Binding(...)` line to add) and when more than one does, because the name is part of the frozen spec and an object with two names has two digests. (3) That name has an entry in `strategies.evidence.EVIDENCE` (`_check_evidence`, checked right after the name is resolved and before any write, dry-run included): a strategy that cannot say, per pick, which numbers its formula used would show picks on the site with no reason, so it is refused with one line naming `seer_engine/strategies/evidence.py` and `EVIDENCE`.
- **The rules must be the `sim.rules` preset of their own id** (`_check_rules`): a roster row carries only `rules_id`, so a one-off `TradeRules` would be frozen under one rule set and read back under another — a `store.SpecMismatch` on the entry's first paper night instead of a refusal here.
- **The engine is dispatched on `sim.rules.is_bracket(rules)`**, not on `rules.engine == "bracket_v0"` (GOTRADE_FEE_REBUILD phase 12): a bracket rule set now has more than one id — `design-v0` and the Gotrade bracket preset — and a string comparison against one of them would promote a bracket candidate as a `book` entry.
- **`find_candidate`** reads `lab.method.discover()`. No committed method file, a multi-variant method named without `--candidate`, and an unknown `--candidate` are each a named `NotPromotable` that lists what does exist.
- **`check_lookback`** raises at promotion time what `commands/paper.py:_check_window` would raise at 23:00 on the entry's first night, so the roster never holds a row the night cannot feed.
- **One `strategies` INSERT**: the display columns, **every** definition column migration 006 added (`object_name`, `registry_id` **NULL**, `gate_note`, `gate_applicable` — `roster.from_row` refuses a row without them, so leaving one out would fail the next night for the whole board), `status = 'active'`, `promoted_from = <method id>`, the full contract-C2 `params` (spec, digest, backtest_gate), and **no `paper_start`**: the next paper night freezes the spec through `paper.store.freeze_spec` and starts the clock exactly as for any new entry, which is what keeps the record honest — a promoted strategy's track record begins when it was promoted. `is_champion` and `is_benchmark` are always false (a promotion never takes the champion from `SPY`); `--sort` defaults to one past the current maximum.
- **The row is proved before it commits**: `_insert` reads it back with `paper_store.read_strategy` and rebuilds it through `roster.from_row` **inside the same transaction**, then compares the rebuilt digest with the planned one. Any `RosterError`, or a digest that moved, aborts the promotion with the night's own message, so a row the paper night would refuse is never committed. (Phase 1 asked for this hook by name.)
- **`--retire <id>`** calls phase 2's `paper.store.retire` in that same transaction, so a swap is atomic and the board never shows five active horsemen or three. `--retire` equal to `--id` is refused outright.
- **The target id**: `_check_target` raises `AlreadyStarted` when the id already has a `paper_start` (invariant 3, add never mutate: months of track record must not be re-pointed at another algorithm) and `RosterConflict` when the id exists and is not this promotion's own row. An existing unfrozen row with the same `promoted_from` **and** the same digest *is* this promotion's own: the insert is skipped and only the lab side is re-recorded.
- **The lab record** is `lab.store.record_promotion(conn, method_id=, strategy_id=, candidate_id=, object_name=, spec_digest=, retired_id=, move_status=, basis=, reason=)`, which returns the method's status. The lab is append-only, so the promotion is *added*: `analysis` grows by one dated `# Promotion` section (`methods_analysis_grows` permits only growth) and one `insights` row of kind `observation` is appended. `status` moves to `paper` **only** along the edge `TRANSITIONS` already has, `('test-passed','paper')`; a method already at `paper` is left alone, and any other status raises `LabError` rather than inventing an edge. It is **idempotent**: a method whose `analysis` already carries `PROMOTION_MARKER` followed by the roster id is already recorded, and the call writes nothing. `hypothesis`, `verdict`, `parent_id` and above all `source_sha` are never written, and no `trials` row is inserted — a promotion is not a backtest and must not move the lab's N. The caller holds the transaction, as for every other writer in that module. Since lab-luck-gate phase 6 the analysis section also carries `Lab status at admission` and `Basis`, plus the override's one-line reason: `basis` left `None` is derived from the method's current status by `promotion_basis`, a basis outside `PROMOTION_BASES` raises, and an `owner-override` with no `reason` raises before anything is written. Idempotence wins over a differing basis or reason on a re-run — what was recorded is what was true on the night of the admission.
- **`--lab-status-stays`** records the promotion and leaves the method's lab status alone. It is required when the method is not at `test-passed` or `paper`, because `TRANSITIONS` has no other edge to `paper`; the roster's admission rule is not the lab's gate (Decisions D3), so taking a method the lab has not passed is allowed but must be said out loud.
- **`--lab-override-reason REASON`** (lab-luck-gate phase 6) is the second half of saying it out loud: one line stating *why* the roster is taking a method the lab has not passed. `lab_store.promotion_basis(lab_status)` reads `test-passed` only from the statuses `test-passed` and `paper`; everything else — `rejected` included — is an `owner-override`, and an override with no reason is refused **before either database is opened for writing**, with the message naming the flag and saying "Neither database was touched." The basis and the reason travel to both sides at once: `build_promotion` puts them on the entry's `roster.LabProvenance` (which refuses an empty reason itself, so the check holds even for a direct caller), `record_promotion` writes `Lab status at admission: … Basis: … <reason>` into the method's analysis, `render_plan` prints a `lab provenance` block on every run, and on a real run the command prints the exact `paper.roster.LAB_PROVENANCE` entry to paste into `roster.py` in the same commit. Forgetting that paste is what `tests/test_paper_roster.py` makes loud.
- **`backtest/registry.py` is never touched** (Decisions D1). `REGISTRY` is the P7a dev-run candidate set, fixed *before* the run, capped at `dev.MAX_CANDIDATES` and digest-pinned; appending to it would corrupt the multiple-testing count the lab's `trials` table exists to maintain. A promoted method reaches the roster through the roster's own resolver, the way `A` and `C` do. Also never written: `paper_start`, any paper history row, any `trials` row, any lab `source_sha`, and any `TRANSITIONS` edge that is not already there.
- **Two databases, one promotion**: the roster is Neon, the lab is `lab/lab.sqlite`, and they cannot share a transaction. So the lab's rules are checked first and write nothing, the roster transaction commits, then the lab record commits (`lab_store.begin_immediate`, rolled back on any exception). The only possible partial outcome is "roster written, lab note missing", and re-running the identical command repairs it, since the insert is skipped for a row this promotion already owns and `record_promotion` is idempotent. The reverse order was rejected: a lab note for a promotion that did not happen cannot be taken back from an append-only database.
- **`render_plan`** prints every row the promotion will write — the INSERT column by column, the `--retire` UPDATE, the two lab writes, and `backtest.registry.REGISTRY untouched` — on every run, dry or not. `--dry-run` rolls back both transactions and says so.
- **Exit codes**: 0 success; 2 for any `PromoteError` (`NotPromotable`, `AlreadyStarted`, `RosterConflict`), `roster.RosterError`, `lab_store.LabError` or `paper_store.StoreError`; 1 for anything else.
- Tests: `tests/test_promote_command.py` and the `record_promotion` cases in `tests/test_lab_store.py` (both extended by lab-luck-gate phase 6 for the basis, the required reason and the printed `LAB_PROVENANCE` line).

### `compare` (roster-promotion-pipeline phase 3)

```
python -m seer_engine compare [--min-sessions N] [--exclude ID ...] [--json] [--require-window]
```

Ranks the paper strategies over the window they **share**, with that window stated rather than
implied. Read-only, and the one impure edge of the pure `paper/compare.py`: it reads every
`equity_snapshots` row in a single `REPEATABLE READ, READ ONLY` transaction that is always rolled
back, hands them to `paper.compare.compare`, and prints the window, the ranking over it, what could
not be ranked and why, and inception-to-date as a separate block. Nothing else is read — no
`strategies` row, no roster, no clock — so `--dry-run` changes nothing because there is nothing to
change.

- **`--min-sessions N`** (default `paper.compare.MIN_COMMON_SESSIONS`, 63; minimum 2) is the floor on
  how short the common window may be.
- **`--exclude ID`** drops a strategy from the comparison. Because the command does not read
  `strategies`, it does not know which entries are retired, and that is deliberate: a retired
  strategy is not a live competitor, so excluding it is a caller's decision, not this module's
  arithmetic. The leaderboard's TypeScript port makes the same decision from `strategies.status`.
- **`--json`** prints `paper.compare.as_json` instead of the table — the exact shape that port is
  pinned against.
- **Exit codes**: 0 when a comparison was produced; with `--require-window`, 1 when no window of
  `--min-sessions` sessions exists (useful in CI, and the honest answer for a young board); 2 for a
  missing setting.

### `lab promote` (build-promotion-path phase 3)

```
python -m seer_engine lab promote M0007 [--dir PATH]
```

Method lab design §3 in one command: it pre-registers a method's best dev-eligible variant for the
test window and moves the method `dev-eligible -> promoted`. It loads no research store, runs no
backtest and inserts no `trials` row, so `store.test_looks` reads the same after it as before —
pre-registering costs no look.

- **Which variant**: `lab.store.best_dev_eligible(conn, method_id)` — the highest `mar` among that
  method's `window = 'dev'`, `eligible = 1` trials, ties broken on the trial number. "One variant per
  method" is a property of that query, not of the caller. A test trial is never a candidate: letting
  one back in would let a test number decide what gets tested.
- **What it writes**: `docs/lab/prereg/M0007.md` (`--dir` relocates it, for tests), one dated
  `# Pre-registration` section appended to the method's `analysis`, one `insights` row of kind
  `observation`, and the status transition. The file is written **first**, inside the write lock, and
  the status moves second in the same transaction — the file write is not rolled back, and that
  asymmetry is the point. A crash between them leaves a pre-registration for a method still reading
  `dev-eligible`, which a re-run finishes, rather than a `promoted` method with nothing
  pre-registered, which is the one state design §3 forbids.
- **The digest is copied, never recomputed** from the live method file: it comes off the recorded dev
  `trials` row, so the file names what was actually measured. `prereg.check_source` separately proves
  the method file still hashes to the `source_sha` frozen when it ran and that the trial's candidate
  still digests to the trial's `config_digest`.
- **Idempotent, and more than idempotent**: a method already at `promoted` is not moved again (the
  forward-only trigger would refuse it anyway) and its analysis is not appended to twice; a
  pre-registration already on disk is read, checked and left **byte-for-byte alone**, date line
  included — rewriting identical-but-for-the-date bytes would un-commit a file whose whole value is
  that it was committed first. A *missing* file is rewritten, which repairs a half-finished promotion.
- **It refuses to change its mind**: when the file, or the method's analysis, already pre-registers a
  different candidate than the one the database now ranks best, that is a `PreregError`. The first
  choice is the one the look is spent on; a genuinely better variant is a new method with its own dev
  trials, not a new version of this file.
- **`--dry-run` is ignored**, as it is for every `lab` subcommand: there is no roll-back half to show,
  and a dry run that printed a pre-registration without writing it would be exactly the artefact
  design §3 exists to prevent.
- **Output**: whether the file was written or already pre-registered the candidate, the method's
  status, the candidate and its dev trial, the config digest, the dev window with MAR / DSR / N, the
  test window, the gate, the `git add` / `git commit` / `lab test` lines to run next, and the
  test-window look count.
- **Exit codes**: 0 success; 2 for any `PreregError` (a `store.LabError`, so `lab`'s existing handler
  already maps it); 1 for anything else.
- Tests: `tests/test_lab_prereg.py` (25) and the `best_dev_eligible` case in `tests/test_lab_store.py`.

### `lab test` (build-promotion-path phase 4)

```
python -m seer_engine lab test M0007-RESID [--store PATH] [--roster-id ID] [--dry-run]
```

The one counted look at the test window (design §3), and the last step before the paper roster. It
is addressed by **candidate**, not by method: one variant per method is pre-registered, and it is
that variant the look is spent on. `runner.resolve_candidate` reads it out of the committed method
file, so `lab test` runs the file, not a database row.

- **It refuses before it loads anything**, in this order (`runner.preflight_test`, every one a
  `store.LabError`): the method is not `promoted` (only `lab promote` moves it there); the method
  file is uncommitted, or no longer hashes to the `source_sha` its dev trials ran under — a changed
  method is a new variation method, not a second look; there is no committed pre-registration naming
  this method and this candidate (`prereg.require_committed`); the pre-registered configuration
  digest has drifted (`prereg.check_digest`); this configuration has no recorded `dev` trial — the
  test window confirms a dev result, it never discovers one; and this configuration has already had
  its look. That last refusal is the readable, early form of a no the database makes anyway:
  `UNIQUE(config_digest, window)` on `trials` plus the append-only triggers. None of them spends
  anything.
- **The store must be the test store.** `--store` defaults to `research.TEST_STORE_DIR`
  (`engine/.research-test`) or `$SEER_RESEARCH_TEST_STORE`. The command asks
  `research.declared_window(store_dir)` what the store is for and refuses a dev store **by name**
  before a data file is read; `load_store` refuses the mismatch a second time, and `run_test` makes
  the same check a third time on `data.window`. Three independent noes, because a `window = 'test'`
  row measured on dev data can never be corrected. A missing store is reported with the
  `research_store --test-window` line that builds it, and a `MarketAware` candidate against a test
  store with no fundamentals panel is refused rather than measured.
- **What a run records**: exactly one `trials` row with `window = 'test'`, appended with the status
  move in one `BEGIN IMMEDIATE` transaction, with `preflight_test` re-run inside the lock so a
  parallel session cannot win the same look twice. The candidate goes through `dev.run_registry` —
  the same path, the same `prepare_for` dispatch and the same D8 row as `lab run`, and since
  lab-realistic-gate R2 the same `sim.contributions.OWNER_MONTHLY` funding, with the window
  as the only difference — so the look is judged money-weighted against a dollar-cost-averaged
  SPY fed the identical dollars on the identical sessions. When the test window contains at least
  one deposit date, a `trial_funding` row is written beside the trial **inside the same
  transaction**: a raise there rolls the look back rather than spending it, and a spent look is
  unrecoverable. The `if cash:` guard is load-bearing for the same reason — `trial_funding` CHECKs
  `deposits_usd > 0`, so an unconditional insert would fail a look that had nothing wrong with it
  on a window with no 25th in it. The funding changes nothing about when or whether the look is
  spent: `insert_trials` is still the first write inside the one `BEGIN IMMEDIATE` and every
  refusal is the same refusal in the same order.
- **It does not move the lab's N.** `n_trials_at_run` is `store.dev_trial_count` as it already
  stands — still, after lab-realistic-gate R1, because this row is a `window = 'test'` row whose
  verdict has no DSR condition at all, so nothing ever deflates by the number stamped on it; only
  `runner.trial_rows`'s **dev** path went through `pending_gate`. `trials` counts the multiple
  testing of the *search*, and a pre-registered look at an
  already-counted configuration is not a new search. `dev_trial_count` and `dev_daily_sharpes` stay
  dev-only, so every recorded dev trial stays reproducible and a later dev trial is deflated by
  exactly the N it would have had if this look had never happened.
- **DSR is recorded and is not a condition.** The verdict is the five design §1 go-live conditions
  (`dev.FAILURE_LABELS`), which `dev.make_row` has already applied; `store.DSR_LABEL` never appears
  in a test trial's `failed`. A pre-registered look has no selection among results to deflate.
- **The method ends final**: `test-passed` or `test-failed`, and `TRANSITIONS` gives `promoted` only
  those two exits. `test-failed` is final on every window — the follow-up is a variation method with
  its own dev trials, not a retry.
- **On a pass it prints the next command rather than running it** (`_promote_argv`): a complete
  `python -m seer_engine promote --method ... --candidate ... --id ... --gate-note ...` line, plus
  `lab stage`. `lab test` reads a research store and a SQLite file and stays offline; `promote`
  opens Neon, and the two writes cannot share a transaction. `--roster-id` sets the id proposed in
  that line (default: the method id). The generated `--gate-note` states both windows and says out
  loud what the method still has not got — forward paper time.
- **`--dry-run`** prints what would run (the method, variant, config digest, the committed
  pre-registration and its date, the store, the five conditions, and both outcomes) and stops. It
  loads nothing, runs nothing and records nothing; the look is not spent. This is the one `lab`
  subcommand where `--dry-run` means something.
- **Output**: the refreshed `lab show` for the method, then the verdict with return vs SPY TR, CAGR,
  max DD, PF, trades, MAR and the recorded DSR at N, then either the promote hand-off or the
  `test-failed` note, then `Lab N (dev trials) is still N; test-window looks used: K`.
- **Exit codes**: 0 success (a `test-failed` verdict is a successful run and exits 0); 2 for any
  `store.LabError`, which is every refusal above; 1 for anything else.
- `lab status` lists `Test-passed` and `Test-failed` as their own sections, next to `Dev-eligible`
  and `Promoted (pre-registered)`. Against the real lab, `test-window looks used` reads **0**: this
  phase builds the mechanism and spends nothing.
- Tests: `tests/test_lab_test_window.py`, with the fixtures in `tests/labkit.py`.

### `lab remeasure` (lab-luck-gate phase 3)

```
python -m seer_engine lab remeasure M0022 [--store DIR]
```

Recovers the DSR's inputs for dev trials recorded before `trial_moments` existed. It re-runs the
method's recorded variants on the **dev** window through the same `dev.run_registry` path `lab run`
uses, proves the re-run *is* the recorded measurement, and appends `trial_moments` rows — and
nothing else. It is addressed by **method**, one at a time, on demand.

- **It writes `trial_moments` and nothing else.** There is no INSERT, UPDATE or DELETE against
  `trials` or `methods` anywhere in `lab/remeasure.py`: no recorded `dsr`, `eligible`, `failed` or
  `n_trials_at_run` moves, no status transition happens, no pre-registration is written. Each row
  carries the trial's **recorded** `n_trials_at_run`, not today's dev trial count — the row
  documents the measurement that was made — and a `measured` stamp of *this* backfill, not the old
  trial's `run_at`, because the moments were measured today on today's store.
- **Two checks, both aborting before a row is written** (`remeasure.check`, all or nothing): the
  freshly measured annualized Sharpe reproduces the recorded `trials.sharpe` to `SHARPE_TOL` (1e-9
  *relative* — full-precision engine floats, so only a last-ulp wobble is expected), and the DSR
  recomputed from the fresh moments, at the trial's recorded `n_trials_at_run` and the
  reconstructed `var_trials` of its run, reproduces the recorded `trials.dsr` to `DSR_TOL` (1e-6
  *absolute* — a DSR is a probability). One divergent trial aborts the whole command: a partial
  backfill would mix moments measured on two different stores inside a table whose point is that a
  verdict can be recomputed from it.
- **The funding is read off the trials, not chosen** (lab-realistic-gate R2). A trial with a
  `trial_funding` row ran on `sim.contributions.OWNER_MONTHLY` and is re-run on it; a trial without
  one ran on a lump sum and is re-run on a lump sum (`runner.recorded_contributions` is the same
  answer by trial number). Getting this wrong is not a small error: an unfunded re-run of a funded
  trial reports an annualized Sharpe of 0.26 against a recorded 2.65, and the Sharpe check above
  then correctly refuses to write anything. A plan that **mixes** funded and unfunded trials is
  refused outright, because one `dev.run_registry` call runs every candidate on one schedule and
  there is no answer that reproduces both. All 128 trials recorded before R2 are unfunded, so every
  backfill the command has ever done is unchanged.
- **`var_trials` was never recorded and is still recovered exactly.** `remeasure.batches_of` groups
  a method's dev trials into the `lab run` batches that wrote them — one batch is one
  `BEGIN IMMEDIATE`, so its `trials.n` are contiguous — and rebuilds the prior daily Sharpes from
  the `sharpe` column of every dev row with a lower `n`. It refuses a non-contiguous batch, and
  refuses one whose recorded N falls outside
  `1 <= n_trials_at_run <= max((dev trials before it) + (batch size), npolicy.DSR_MIN_N)`, because
  then the recorded N does not describe the batch and no honest `var_trials` can be rebuilt from
  it. **The upper bound was an equality until 2026-10-08** (lab-realistic-gate R1): the row-count
  expression is the `all-trials` projection, so once `store.DSR_POLICY` moved to `"methods"` an
  equality would have refused every batch recorded under any policy but that one — testing the
  policy rather than the batch. As a bound it still says the only thing the rows can prove: a
  recorded N above the number of looks that existed when the batch was judged cannot describe it,
  and no policy counts more than one look per row. Widening it loses nothing, because the quantity
  this function reconstructs — `prior_sharpes`, and through it `var_trials` — is read from the rows
  with `n < first` and never from `n_trials_at_run`, which is carried through verbatim into the
  rebuilt `MomentsRow`; and the DSR check below already refuses and writes nothing when the
  recomputed DSR does not reproduce the recorded one. The `DSR_MIN_N` term widens the ceiling only
  on the degenerate one-trial lab, where `effective` floors at 2 and the row count is 1.
- **It refuses before it loads anything** (`remeasure.preflight`, every one a `store.LabError`): the
  method has a `window = 'test'` trial — the look is spent and nothing here may stand near it; the
  method has no dev trial; a trial recorded no DSR or no Sharpe, so a re-run cannot be checked
  against it; the method file is uncommitted, or no longer hashes to the `source_sha` its trials ran
  under; a recorded configuration the method file no longer defines. `resolve_method` refuses an
  `H-*` seed family by shape (no method file, no recorded DSR) and an unknown method id.
- **The test window is unreachable by construction, not by care**: the test-window refusal is made
  first, `research.load_store` is called with no window so it defaults to `DEV_WINDOW` and refuses a
  test store **by name** before a byte is read, `measure` refuses a loaded store whose window is not
  `research.DEV_WINDOW`, and `dev.run_registry` is called with no `window` keyword — neither
  `measure` nor `remeasure` has a parameter with which to pass one. `--store` defaults to
  `research.STORE_DIR` or `$SEER_RESEARCH_STORE`.
- **Idempotent**: when every dev trial already has its moments it prints what it skipped and returns
  *without loading a research store* — re-loading a 135 MB store and re-running backtests to write
  nothing is not idempotence. `trial_moments` is append-only, so "already there" is the answer,
  never a rewrite; `preflight` runs again inside the write lock so a parallel session that
  backfilled the same method in between is not written over.
- **`--dry-run` is ignored**, as it is for every `lab` subcommand but `test`.
- **Output**: one line per trial with its fresh `(sr_daily, t, skew, kurt, var_trials)` at `N`,
  the recorded vs measured Sharpe and the recorded vs recomputed DSR with both deltas and
  tolerances, the trials left alone, and then `Lab N (dev trials) is still N; test-window looks
  used: K` — both unchanged by this command.
- **Exit codes**: 0 success (including the nothing-to-do run); 2 for any `store.LabError`, which is
  every refusal above and an unknown method; 1 for anything else.
- Measured: `lab remeasure M0022` reproduced all three recorded DSRs bit-identically.
- Tests: `tests/test_lab_remeasure.py` (13), with the fixtures in `tests/labkit.py`.

### `lab remeasure H-P7A` — the seed path (lab-luck-gate phase 9)

```
python -m seer_engine lab remeasure H-P7A | H-P7A-F9 [--store DIR] [--only IDS] [--chunk N]
```

The same command, addressed at the **P7a seed** instead of a lab method. Fifty-four of the lab's
110 dev trials were imported from the P7a exploration with `dsr IS NULL` (`lab/seed.py`: "P7a
reported it for one row only"), so they paid the full multiple-testing penalty and received no
verdict in return — permanently ineligible by *data gap* rather than by merit. This path measures
their daily moments and writes `trial_moments` rows, so the gate can finally judge them.
`H-P7A` is every family; `H-P7A-F9` is one.

- **It raises the bar for nobody, and that is the point** (design §7.6, invariant 7). The 54 are
  *already* inside `dev_trial_count`, and this writes **no `trials` row** — only
  `store.insert_moments`. Phase 9 asserted all four quantities before and after a full 54-row
  batch: `dev_trial_count`, `npolicy.effective_n(conn, 'all-trials').n`, `dev_sharpe_variance`
  and `dev_daily_sharpes` are identical, and the committed `lab/lab.sqlite` is byte-unchanged.
- **Resumable, idempotent and chunk-invariant** (`remeasure_seed`, `run_chunk`). Each chunk is
  re-run, verified and committed before the next starts, so an interrupt loses at most the chunk
  in flight. `plan.todo` holds only trials with no moments row and is re-read inside each chunk's
  write lock, so a parallel explorer that wrote the same rows is a **skip**, not a conflict.
  `plan.var_trials` is read off the database once in `seed_preflight` and never off the re-run,
  which is what makes the output independent of where the chunk boundaries fall. A second run
  writes nothing and loads no research store. `--chunk` defaults to `dev.MAX_CANDIDATES` (60).
- **A divergent trial is reported, not raised, and is not written** — the one deliberate
  difference from phase 3's all-or-nothing `check`. Phase 3 measures two to five trials of one
  method together; here a single drifted ETF would otherwise sink fifty-three sound
  re-measurements across eleven unrelated families.
- **The tolerance is absolute, not relative** (`METRIC_TOL = 1e-6`, over the six metrics in
  `SEED_METRICS`). The recorded rows come from a CSV written to six decimal places, which bounds
  the recorded-vs-true error at 5e-7 *absolute* regardless of magnitude; a relative bound would be
  the wrong shape at both ends of the range. Measured worst delta across all 54: **4.986e-07**.
- **It reads the frozen P7a registry and never writes it** (`REGISTRY_FILE`); it refuses the test
  window by name, like every other `remeasure` path.
- **The report prints two DSRs side by side, and only one is a verdict** (`seed_verdicts`,
  **Decision D12**). `v.dsr` is the gate's number — `store.dsr_at` deflating by
  `store.dev_sharpe_variance(conn)`, today's variance over all 110 dev trials, on both routes.
  `dsr_recorded_var` is the same measured moments deflated by the `var_trials` recorded beside
  the trial, and **must never be read as a verdict**; it is printed so the size of the choice
  stays on the terminal. The seed rows are the only place in the lab where the two differ
  materially — 2.0067e-04 against 2.3950e-04 — and they move `F9-SPY200M70-MOM30` from
  **0.8567** (the gate's number, which fails) to 0.9031 (which would have passed).
- **Net effect**: `F9-SPY200M70-MOM30` passes every owner condition at the new 20% bar and is now
  held out **on a luck test it finally received**, rather than on a data gap — which is R6
  satisfied either way. The eligible set stays **three**.
- Measured: all 54 in ~65 seconds (10.8s to load the store, 51.5s of backtests).
- Tests: `tests/test_lab_remeasure_seed.py` (16).

### `lab reevaluate` (lab-luck-gate phase 4)

```
python -m seer_engine lab reevaluate [M0022 ...]
```

Re-judges recorded dev trials against the bars in force **now** — `store.DSR_MIN`,
`store.DSR_POLICY` and `tuning.MAX_DRAWDOWN` — and moves a method those bars unblock from
`rejected` to `dev-eligible`. With no argument it sweeps every method that reads `rejected`.

- **It reads only the database.** No research store is loaded, no backtest runs, no `trials` row is
  inserted, updated or deleted, so the lab's N does not move and `test_looks` is untouched. Every
  recorded `dsr`, `eligible`, `failed` and `n_trials_at_run` still reads exactly as it did —
  including the `DSR >= 0.95` and `max DD <= 15%` labels that rejected a method, which name the
  bars of their own day. What is written is two things: one dated `# Re-evaluation` section
  appended to the method's `analysis` (append-only by trigger, the shape `record_promotion` uses)
  naming the threshold, the policy, the N and the date that re-judged it, and the `status` column.
- **One edge, from one status** (`store.TRANSITIONS` gains `('rejected','dev-eligible')`, Decision
  D2). "Status moves forward only" protects verdicts from being *erased*, and nothing here erases
  one: the trials that decided the rejection stay in the append-only `trials` table and the
  re-evaluation is appended, not rewritten. Without the edge the loosened bars would be
  unreachable — the methods they unblock already read `rejected`, and re-judging one under a new id
  would need a duplicate configuration digest, which `has_trial` refuses outright. A method at any
  other status is left alone (`moved` False), and there is no second edge in, so nothing moves
  twice.
- **Twice guarded, on purpose.** `store.verdict` derives the five conditions; `store._blocking`
  then repeats the four threshold comparisons against the same live constants **in its own code**
  and refuses outright when the recorded `failed` carries `owner inputs`. Two owner-set bars moved
  in this plan set (the luck threshold here, the drawdown bar in phase 8), and a gate that loosens
  on two axes at once is worth two noes written in two places: a trial that reads derived-eligible
  but does not clear the second check is a contradiction inside the module and raises `LabError`
  rather than promoting quietly. The rule is about the numbers, not the string — `M0020-W-NOSTOP`
  recorded `"max DD <= 15%; DSR >= 0.95"` and *should* move, because the owner moved both of those
  bars.
- **Neither the threshold nor the policy is a flag.** A write path that could unblock a method
  under any bar on request would make both constants decorative. The read-only comparison across
  policies is phase 5's `lab luck`; the pairing is deliberate and the names are deliberately not
  neighbours — **`lab reevaluate` writes, `lab luck` reads**.
- **A trial whose DSR cannot be evaluated fails the luck test** and is counted and named per
  method rather than passed over in silence — the 54 P7a seed rows, whose `dsr` is NULL by
  construction, are the case that matters.
- **`--dry-run` is ignored**, as it is for every `lab` subcommand but `test`. The whole sweep is
  one `BEGIN IMMEDIATE` transaction: either every method it unblocks moves, or none does.
- **Output**: the luck bar, the policy and the N (with the dev trial row count beside it), then one
  line per method — moved, no dev trial, no evaluable DSR anywhere, or re-judged and unchanged —
  then `K method(s) moved rejected -> dev-eligible; test-window looks used: 0`. When anything
  moved it prints the `lab export-json` line to refresh `web/data/lab.json` and says to commit it
  with `lab/lab.sqlite` (`export-json`, not `stage`, because `lab stage` also `git add`s and the
  swarm shares one worktree).
- `lab status`'s "misses" column now comes from `store.owner_failures(row)` rather than from
  splitting the row's `failed` string and dropping `DSR_LABEL`: the string names the bars of the
  run date, and both of them have since moved.
- **Exit codes**: 0 success (a sweep that moves nothing is a successful run); 2 for any
  `store.LabError`, which is every refusal above; 1 for anything else.
- Tests: `tests/test_lab_gate_policy.py` (33) — the derived verdict, the two routes to a DSR, the
  three unblocked candidates, the near misses that stay out, and the proof that
  `(all-trials, 0.95, 15%)` reproduces the previous verdicts exactly. Since lab-realistic-gate R1
  the `lab_n110.sqlite` fixture is judged under the policy its 110 rows were **recorded** under:
  the `committed` fixture pins `DSR_POLICY = "all-trials"` beside the database it describes, the
  hand-built one- and two-method labs take an explicit `at_all_trials` where the rule under test
  needs a row-counting N, and exactly one test — the one whose subject *is* the shipped default —
  uses the unpinned `committed_unpinned` copy. Re-pointing the N = 110 claims at the new policy
  would delete the record of what the two moved bars did rather than test anything; what the
  shipped policy resolves to is pinned in `test_lab_npolicy.py` and in
  `test_pending_gate_reproduces_todays_n_under_the_shipped_policy`, which is R1 as one assertion —
  a batch of variants of a known method adds **0** to N and a brand-new method adds exactly **1**.


### `lab luck` (lab-luck-gate phase 5)

```
python -m seer_engine lab luck [--at N ...] [--limit K]
```

The dev-trial leaderboard under every N policy, side by side, so the gate's sensitivity to N is
inspectable **without editing `store.DSR_POLICY` and re-running anything**. It reads the lab
database and nothing else.

- **A column per policy, plus a column per `--at N`.** Each named policy is resolved to its N with
  the evidence for that N printed beside it; `--at` is repeatable (`lab luck --at 37 --at 23`) and
  its columns are never deduplicated against a policy that happens to land on the same N — the
  reader asked for a column at a literal N and gets one, labelled by the N. `--limit K` caps the
  listing (default 12, `0` for all), ranked by the DSR at the **live** policy's N, ties by trial
  number, so the order is a property of the command and not of insertion order.
- **Recovered, not re-run.** `DSR = Phi((SR - SR*(N)) * k)` and `k` does not depend on N, so each
  recorded DSR is re-evaluated at another N by inverting it at the N it belongs to
  (`store.recover_dsr`, phase 4's, re-exported here with `sr_star`). `recover_dsr` returns the
  recorded value exactly at `n_at_run`, so the `recorded` column reproduces the database
  bit-for-bit and the other columns move nothing but the multiple-testing count. **It is not a
  verdict** — the verdict is `store.verdict`, which recomputes exactly from `trial_moments`.
- **Per policy it reports** the N, the daily hurdle `SR*(N)`, how many candidates clear
  `store.DSR_LABEL` there and which, and an `evidence:` line read **generically** off that
  policy's `npolicy.NCount` (participation ratio, mean pairwise correlation, whatever phase 1
  names next) — phase 1 owns those field names, and the evidence behind an N is exactly the
  thing that must not go stale here. The header carries the dev trial count, the test-window
  looks used, the live policy and the trial-Sharpe variance now (with its sd and the number of
  dev trials carrying a Sharpe): the deflation's own inputs, printed rather than assumed. A
  policy that cannot be resolved on this database keeps its row with the reason instead of
  vanishing — `lab luck` is what you run when the gate is behaving oddly.
- **Trials with no recorded DSR are not listed**: the 54 P7a seed rows carry `dsr IS NULL` by
  construction, there is nothing to re-evaluate for them, and putting a number where the record
  has none is the opposite of what this command is for. With fewer than two dev trials carrying a
  Sharpe there is no variance to deflate by and no leaderboard — it says which of the two reasons
  it is and exits 0.
- **`lab reevaluate` writes, `lab luck` reads.** The pairing is deliberate: neither the threshold
  nor the policy is a flag on the write path, because a write that could unblock a method under
  any bar on request would make both constants decorative. `--at` exists only here, where nothing
  is written.
- **Read-only, by measurement.** No research store is loaded, no backtest runs, no row is
  inserted, updated or deleted, no status moves: `lab/lab.sqlite`'s md5 is unchanged across a run
  and `store.test_looks` still reads 0.
- Measured, **at the lab of 110 trials this was written against**: exactly three candidates clear
  the bar at N = 110 — `M0022-W-TV14`, `M0022-W-TV16` and `M0020-W-NOSTOP` — and pulling the N
  lever to that lab's distinct-method count of 23 admits all seven of the luck-only sample, 18 of
  25 over the whole database. That was phase 5's argument for leaving the lever alone, and
  **lab-realistic-gate R1 pulled it anyway** on 2026-10-08: not because the admission count became
  acceptable, but because `all-trials` asserts an independence the lab's own estimator contradicts
  and because one look per variant *run* made re-running a method perturb every other method's
  verdict. `tests/test_lab_luck.py` keeps both literals deliberately — they are the two N's of the
  lab the sample was taken from, the measured record of what the move costs, stated in advance, and
  not the live gate's N (28 under `methods`).
- **Exit codes**: 0 success; 2 for any `store.LabError`; 1 for anything else.
- Tests: `tests/test_lab_luck.py` (17).

### `lab status`: the promotion path, always printed (lab-luck-gate phase 5)

`_promotion_path` prints every step of `dev-eligible -> promoted -> test-passed -> paper` on every
run, under a header naming the luck bar, the policy and the N in force. A step with methods lists
them under its count and what moves them on; an **empty** step prints `(none)` and one sentence
from `_empty_reason` saying why — for every step but the first that is the step before it and the
command that would move it, and for `dev-eligible` it is the gate itself: nothing has run, or
nothing passes the five go-live conditions (naming the closest and what it misses, and that no N
or threshold can rescue it), or candidates pass all five and the luck bar alone is holding them
(naming the closest, its derived DSR and the bar). Hiding the empty path was the bug: a reader
could not tell a lab with no candidates from a lab whose candidates were one bar away.

- **`Promotable now`** is what `lab promote` would take today — `store.best_dev_eligible` under the
  live policy, with each method's MAR, derived DSR, N and policy — read from the *derived* verdict,
  not the recorded `eligible` column, which was frozen at a 0.95 bar and whatever N its day had.
  A method whose best trial is derived-eligible but whose status still reads `rejected` is listed
  separately as held by the status machine, with `lab reevaluate <id>` named as the one command
  that moves it (**not** `lab run`, which refuses a method whose variants already have dev trials).
- **The D1b ratchet warning** fires when the best candidate passing all five owner conditions is
  within `_WARN_MARGIN` (0.03) of the bar. It prints the margin at the current N, the N at which
  that candidate's DSR falls back below the bar (bisected on the gate's own `recover_dsr` curve,
  seeded from `store.verdict`, e.g. *falls below the bar at N = 143: 33 more dev trials*), and,
  when the lab has at least three run days, how many run days that is at the median dev trials per
  run day measured from `trials.run_at` — no constant lifted from the analysis document. It is a
  sentence, not a gate: nothing refuses to run because of it, and it is silent when no candidate
  is above the bar or the margin is comfortable. The threshold bought the margin; the search
  spends it.
- **`Test-window looks used: k`** closes the block, with the one-look rule beside it (design §3).
- Read-only and measured to be so: `lab/lab.sqlite`'s md5 is unchanged across a `lab status`, and
  `store.test_looks` still reads 0.
- Tests: `tests/test_lab_status.py` (12).

### `lab costs` (Sean phase 7)

```
python -m seer_engine lab costs M0007 [--candidate M0007-N20-RAW] [--store DIR]
```

Report only. Re-runs a recorded method's best dev variant (by MAR, ties to the lower trial
number; or the one named by `--candidate`) twice on the dev window — at the lab's flat 0.1% a
trade and at Gotrade's real fees (`sim/costs.py`) — prints both side by side, and appends one
`observation` to the lab journal on that method.

- Refusals (`store.LabError`, before the store loads): not a lab method id or no committed method
  file; no dev trial; a `--candidate` with no dev trial; a recorded variant missing from the method
  file; a non-book (design-v0 bracket) variant; a variant with its own `cost_rate`. A test-window
  store is refused, and `research.DEV_END != dev.DEV_END` is refused.
- The side the lab recorded is the candidate itself; its twin differs only in `rules.cost_model`
  and carries a `-GT` or `-FLAT` suffix. It exists only in memory, so no method file or digest
  changes.
- The report says whether the recorded side reproduced the trial's total return (`REPRO_TOL`,
  relative 1e-9). If it did not, the store or engine changed, and the two re-runs still compare
  with each other. For that claim to mean anything the re-run must be the same measurement, so
  since lab-realistic-gate R2 `real_costs.measure` takes a `contributions=` keyword and the command
  fills it from `runner.recorded_contributions(conn, trial["n"])` — the funding the **recorded**
  trial ran on, None for all 128 trials recorded before the lab was funded. Re-running a funded
  trial unfunded lands on a different total return, and the report would then announce that the
  store or the engine changed when neither did. Both cost models are fed the identical schedule, so
  the flat/Gotrade comparison stays a comparison of one variant at two fee models and nothing
  else.
- Since trial-reproducibility it also runs at the trial's **recorded capital**
  (`runner.recorded_capital`), not the live `INITIAL_IDR`. Measured 2026-10-09: the +545.3% that
  `lab costs M0011` printed against trial #90's +660.2% was the flat re-run starting at 10M where
  the trial started at 20M; at the recorded capital the flat column reads +660.2% and the report
  says the re-run reproduces it.
- Writes no `trials` or `trial_moments` row and no status. It prints the lab's N and
  `test_looks` before and after, and they are equal. A re-measure can never make a method
  eligible: a real-fee configuration is judged only through a new method (M0031 on).
- Afterwards, solo runs `lab stage` so seertrade.site/sera shows the observation. A Sera child
  leaves staging to its coordinator.
- Tests: `tests/test_lab_costs.py` (15).

### `lab names` (GOTRADE_FEE_REBUILD phase 8)

```
python -m seer_engine lab names [--ns 5,10,15,20,25,30] [--gotrade-only] [--lump]
                                [--csv PATH] [--store DIR]
```

Report only, and the most report-only command in the lab: it writes **nothing at all** — no
`trials` row, no `trial_moments` row, no `insights` journal entry and no status — so the lab's dev
trial count and the test-window looks do not move (126 and 2 at the time of writing; since the
`methods` policy of 2026-10-08 that row count is no longer the gate's N, which is 28 — the
invariant this command asserts is still the right one, but `name_count.py`'s docstring and this
command's output call `dev_trial_count` "the lab's N" and now say so loosely), and `lab/lab.sqlite` is
byte-identical afterwards. Unlike `lab costs` it does not even journal an observation, so
`lab stage` is not needed and seertrade.site/sera does not change. The command prints N and
`test_looks` before and after, so the invariant is visible and not merely asserted in a test.

What it sweeps is the roster's own book. `M0007-N20-RAW` is what the roster's RAW-FR entry trades,
and its `20` is a *parameter* (`ResidParams.inner.top`), so `lab/name_count.py` imports `RESIDMOM`,
`TREND` and `ResidParams` from the frozen method file and builds one in-memory `Candidate` per
(cost model, name count) — `M0007-N<nn>-RAW-GT` and `-FLAT`. The method file, its `source_sha` and
its recorded config digests are untouched, the same thing `paper.roster` does with that file.

Both axes are on because they interact: the runs are at `cost_model="gotrade"` — the fee floor is
size-dependent, so a sweep at the lab's old flat 0.1% would measure a world where a name is nearly
free — and on the owner's real contribution schedule (`sim.contributions.OWNER_MONTHLY`: 10,000,000
IDR at the start, +5,000,000 IDR on the 25th of every month), scored with the money-weighted return
(`backtest.metrics.Metrics.mwr`) against a dollar-cost-averaged SPY, because a book that is fed
money has no honest CAGR and no meaningful "beats SPY TR". `--gotrade-only` drops the flat control
column; `--lump` funds the book once and never feeds it. Each is a control for one axis, not the
answer.

- Refusals (`store.LabError`, every one raised before the research store loads): an empty or
  non-numeric `--ns`; a count outside 2..60; a missing `sim.contributions` or `OWNER_MONTHLY`; a
  `dev.run_registry` that takes no `contributions` keyword; `research.DEV_END != dev.DEV_END`; a
  missing store; and a test-window store — a name count has never been pre-registered, so it may
  not spend a look.
- `Sweep.best(model)` ranks by MAR, ties to the smaller book — the lab's own rank key, the one
  `lab costs` and `dev.finalists` already use — so the grid is read on a measure chosen before
  seeing it. `Sweep.agrees` says whether the two cost models pick the same count.
- **The measured answer (2026-10-08, research store `399d0d254c7a`; write-up
  `docs/backtests/2026-10-08-how-many-names.md`, full-precision grid
  `docs/backtests/2026-10-08-how-many-names-grid.csv`): twenty names, on the merits and not on
  fees.** Five names gives up 1.3 points of money-weighted return a year and falls 37% from a peak
  against 20%; 25 and 30 land within half a point of 20. SPY fed the same money earned 7.19% a
  year, and every count beat it. The two cost models split between 20 and 30 by 0.004 MAR against
  a 0.35 spread across the range, so the fees do not choose the name count — what they do is cost
  the book about 1.3 points a year at *every* count, which is the larger finding. The roster keeps
  N = 20 regardless (GOTRADE_FEE_REBUILD Decision D3): this phase promotes nothing and proposes no
  roster change.
- Six free looks at six name counts is exactly the search the luck gate exists to charge for, so
  this grid may *inform* a decision and may never *be* one. Acting on it means a new method that
  pre-registers the count — which from M0031 on `real_costs.real_cost_problem` already forces to
  run at Gotrade's real fees — and that method pays its trials like any other.
- Tests: `tests/test_lab_name_count.py` (19).

### `lab unblock` (eodhd-survivorship-market phase 3)

```
python -m seer_engine lab unblock MNNNN --note "what arrived and how much of the dev window it covers"
```

The command for the `blocked-data -> idea` edge `store.TRANSITIONS` already allowed ("the missing
data arrived"), the counterpart of `lab block`. It refuses (`store.LabError`, exit 2) an empty
note, an unknown method and a method that is not `blocked-data`. Otherwise, in one transaction, it
appends `Unblocked: the missing data arrived. <note>` plus what the method was blocked on to the
analysis (`store.append_analysis`), then sets the status to `idea` and clears `blocked_on`, so the
analysis is the only place that history survives. Tests: `tests/test_lab_unblock.py` (3).

### `sean marks` (Sean phase 4)

```
python -m seer_engine [--dry-run] [-v] sean marks [--now ISO8601]
```

Marks the owner's real Gotrade holdings to market and rewrites Sean's daily profit/loss series.
It is independent of paper trading and reads no roster or strategy table.

1. `end = dates.last_completed_session(now)`. `--now` pretends the clock is that time (UTC if no
   offset), for tests and replays.
2. Read every `sean_orders` row in a short transaction. If there are none, it takes the lock,
   empties `sean_equity` (so a stale series never outlives deleted orders), logs "no orders yet"
   and exits 0. It fetches nothing.
3. With no transaction open, fetch `[first trade date, end]` closes from Yahoo for each symbol
   ever traded (`equity.symbol_starts` → `marks.fetch_closes`). Owner symbols need not be in the
   universe and may be delisted, so `bars` is not used. A symbol that raises or comes back empty
   is logged and listed as missing. It **never fails the run**: its earlier stored closes still
   stand, and with none the ledger values it at its last order price.
4. In one transaction: `equity.lock` (`LOCK TABLE sean_marks, sean_equity IN EXCLUSIVE MODE`), then
   `marks.upsert_marks` (writes new or changed closes only). Then it **re-reads the orders under
   the lock**, so an upload that landed during the download is counted. It then calls
   `equity.series(orders, end, marks.read_marks(conn))`, one point per NYSE session from the first
   trade date through `end`, and `equity.replace_equity` (delete all, insert all).
5. Log one line: symbols priced, symbols without prices (named), closes written, sessions, the
   last profit/loss.

`--dry-run` does all of the above and rolls back. Exit codes: 0 on success (missing prices
included), 1 on any other error.

Callers:
- `.github/workflows/sean.yml`: `workflow_dispatch` with a `dry_run` input. It runs `migrate` and
  then `sean marks` under its own concurrency group `sean-writer`, not `seer-db-writer`, because a
  queued Sean run there would cancel a pending nightly retry. The site dispatches it right after a
  batch of order screenshots is uploaded.
- `.github/workflows/nightly.yml`: the last step, "Sean marks", with `continue-on-error: true`, a
  10-minute timeout, and `if: success() || steps.paper_check.outcome == 'failure'` (it runs after a
  red Paper check, like Explain). A Yahoo outage or a crash only leaves Sean's graph a day behind.

### `sean calibrate` (Sean phase 7)

```
python -m seer_engine sean calibrate
```

Checks whether `sim/costs.py` still charges what Gotrade charged. It reads every `sean_orders`
row, oldest first, and asks `costs.fee_parts(side, amount, on=<receipt WIB date>)` what the order
should have paid. Then it prints one line per order, paid against schedule for trading,
regulatory and VAT (PPN), and a closing sentence.

- Exit 1 when any order dated on or after `GOTRADE.current.since` is off by more than
  `TOLERANCE` ($0.01) in any part. That means Gotrade changed its fees or the fit was wrong: add
  a new dated regime to `sim/costs.py` and never edit a past one. Orders under an older regime
  are printed with their residual and never fail the check. Exit 0 otherwise, including with no
  orders, or with none in the current regime.
- Dates are WIB calendar dates, which is what the regime boundaries were fitted to. They are
  deliberately not the ledger's New York trade date.
- Read-only. The read transaction is rolled back, and nothing is written.
- Tests: `tests/test_sean_calibrate.py` (15).

## Exported API

### config

- `REPO_ROOT: Path`: the repository root, derived from the file's location.
- `class ConfigError(RuntimeError)`: raised when a required setting is missing. The CLI maps it to exit code 2.
- `env_file() -> Path`: `$SEER_ENV_FILE`, else `<repo>/.env.local`.
- `load_env() -> Path | None`: loads the dotenv file without overriding variables that are already set. Returns `None` when the file is absent (CI). Safe to call more than once.
- `get(name) -> str | None`: the value of `name`. Empty counts as unset. Calls `load_env()` on first use.
- `require(name) -> str`: like `get`, but raises `ConfigError` with the variable name and the dotenv path it checked.

### db

- `CONNECT_TIMEOUT_S = 15`
- `connect(url=None) -> psycopg.Connection`: opens a connection with autocommit off. Defaults to `DATABASE_URL_UNPOOLED` (Neon's direct endpoint, because the pooled one drops session state such as temp tables).
- `transaction(conn, dry_run: bool)`: a context manager. Commits on success. On any exception, including `BaseException`, it rolls back and re-raises. With `dry_run` it rolls back after the block completes.

### http

- `USER_AGENT = "seer-engine/0.1.0"`: set on the shared session. Wikipedia returns 403 to the default python-requests agent.
- `class HttpError(RuntimeError)`: has a `.status` attribute (`int | None`).
- `redact(url) -> str`: replaces the value of any `api_key`/`apikey`/`access_token`/`token`/`key` query parameter with `REDACTED`.
- `get_json(url, params=None, *, retries=3, backoff=5.0, timeout=30) -> dict`: GETs a JSON object. Connection errors, timeouts, 429 and 5xx responses are retried with exponential backoff (`backoff * 2**(n-1)`). A numeric `Retry-After` header wins when it is longer. Any other non-200 status, non-JSON body or non-object JSON raises `HttpError` at once. Every URL in logs and exception messages is redacted.

### dates

All dates are `datetime.date`. The only timezone-aware datetimes are the UTC "now" and NYSE closes.

- `CALENDAR = "NYSE"`, `DEFAULT_SETTLE = timedelta(hours=1)`
- `@dataclass(frozen) RunDates(data_date: date, session_date: date)`
- `sessions(start, end) -> list[date]`: inclusive, ascending. Returns `[]` when `end < start`.
- `is_session(d) -> bool`: half days count as sessions.
- `next_session(d)` / `prev_session(d) -> date`: strictly after or before `d`. Scans up to 3 years, then raises `ValueError`.
- `session_close_utc(d) -> datetime`: the scheduled close in UTC, accounting for half days and DST. Raises `ValueError` when `d` is not a session.
- `last_completed_session(now_utc, settle=DEFAULT_SETTLE) -> date`: the latest session whose close plus `settle` is at or before `now_utc`. Requires an aware datetime (`ValueError` otherwise).
- `run_dates(now_utc=None, settle=DEFAULT_SETTLE) -> RunDates`: `data_date = last_completed_session(now)` and `session_date = next_session(data_date)`.

Passing a `datetime` where a `date` is expected raises `TypeError`, because `datetime` is a `date` subclass and would otherwise slip through.

### prices

Pure value types for prices, with no database import, so the simulator can use `Bar` without loading `psycopg`. `bars` re-exports all three names, so `from seer_engine.bars import Bar, PRICE_QUANTUM, to_decimal` keeps working.

- `PRICE_QUANTUM = Decimal("0.0001")`
- `@dataclass(frozen, slots) Bar(symbol, date, open, high, low, close: Decimal, volume: int)`
- `to_decimal(x) -> Decimal`: rounds half-up to 4 dp. Floats go through `repr`, so `0.1` becomes `0.1000`. Raises on bool and non-finite values.

### bars

Prices are split-adjusted only (no dividend adjustment) and stored as `numeric(12,4)`. Volume is an `int`. Symbols use the canonical dot form (`BRK.B`).

- `PRICE_QUANTUM`, `Bar`, `to_decimal`: defined in `prices` and re-exported here unchanged.
- `to_volume(v) -> int`: rounds half-up. Raises on bool, non-finite and negative values. Massive reports volume as a float.
- `make_bar(symbol, d, o, h, l, c, v) -> Bar`: validates and rounds. Raises `ValueError` for an empty symbol and `TypeError` for a non-date or datetime `d`.
- `upsert_bars(conn, bars) -> int`: COPYs into the temp table `_seer_bars_in`, then runs `INSERT ... ON CONFLICT (symbol, date) DO UPDATE ... WHERE ... IS DISTINCT FROM`. Returns the number of rows inserted or changed. An identical re-run returns 0 and creates no new row versions (`xmin` is unchanged). Raises `ValueError` when a batch holds the same `(symbol, date)` twice.
- `latest_bar_date(conn, symbol) -> date | None`
- `delete_bars_on(conn, d) -> int`

### fx

- `FRANKFURTER = "https://api.frankfurter.dev/v1"`, `PARAMS = {"base": "USD", "symbols": "IDR"}`. These are ECB reference rates and need no API key.
- `fetch_latest() -> (date, Decimal)`: the newest rate and the date Frankfurter assigns to it.
- `fetch_range(start, end) -> list[(date, Decimal)]`: inclusive and ascending, with one request per calendar year.
- `upsert_fx(conn, rows) -> int`: has the same temp-table and `IS DISTINCT FROM` shape as `upsert_bars` (`_seer_fx_in`). An identical re-run returns 0. Raises `ValueError` on conflicting rates for one date in a batch. A missing IDR rate in a response raises `ValueError`.

### yahoo (phase 3)

This is the only module that knows Yahoo's ticker spelling. Prices come from yfinance's `Open/High/Low/Close/Volume` with `auto_adjust=False`, so they are split-adjusted but not dividend-adjusted. `Adj Close` is ignored on purpose.

- `Downloader = Callable[[list[str], date, date], DataFrame | None]`: `(yahoo_tickers, start, end_exclusive)`. Tests inject a fake and never touch Yahoo.
- `class RateLimited(Exception)`
- `to_yahoo(symbol)` / `from_yahoo(ticker) -> str`: `BRK.B` and `BRK-B`, upper-cased and stripped.
- `yf_download(tickers, start, end_exclusive)`: the real downloader. One `yf.download` call (`interval="1d"`, `group_by="ticker"`, `threads=False`, `repair=False`). `yf.download` swallows per-ticker errors and only logs them, so a temporary handler on the `yfinance` logger captures ERROR records. A rate-limit message there, or a raised `YFRateLimitError`, raises `RateLimited`.
- `download(symbols, start, end_exclusive, *, downloader=None) -> dict[str, list[Bar]]`: one entry (possibly empty) per requested canonical symbol, with bars sorted by date. The caller filters to its inclusive range, because Yahoo can return a partial current-day bar.
- `parse_frame(frame, tickers)`: accepts `(Ticker, Price)` or `(Price, Ticker)` MultiIndex columns, and flat columns when exactly one ticker was requested.
- `frame_to_bars(symbol, sub) -> list[Bar]`: drops rows with missing or non-finite OHLC and rows with a non-positive price. A missing volume becomes 0. A tz-aware index is made naive without conversion, so the exchange-local date is kept.

### runs

- `MAX_ERROR_CHARS = 2000`
- `start_run(conn, rd: RunDates) -> int | None`: claims the real run row for `rd.session_date` and sets `status='running'`. Returns `None` when that session already has a successful real run, in which case the caller does nothing. A failed or stale running row is reused with the same id: error and `finished_at` are cleared and `data_date` is refreshed. This relies on the `runs_real_session_uidx` partial unique index.
- `finish_run(conn, run_id)`: sets `success` and `finished_at = clock_timestamp()`.
- `fail_run(conn, run_id, error)`: sets `failed` with a redacted error cut to 2000 characters.
- Both final setters raise `LookupError` when `run_id` is not a real (non-demo) run.
- P4: `start_paper(conn, run_id)`, `finish_paper(conn, run_id)`, `fail_paper(conn, run_id, error)` (error redacted, cut to 2000 characters); each raises `LookupError` for an unknown or demo run. `paper` sets `running` in a short transaction of its own, then `success` inside the night's transaction; a failure rolls the night back and sets `failed` with a redacted `paper_error` in its own transaction.

### universe (read side only; phase 2 writes the table)

Membership intervals are `[start_date, end_date)`, where `end_date` is exclusive and NULL means still a member.

- `BENCHMARK = "SPY"`
- `members_on(conn, d) -> set[str]`: symbols in either index (SP500 or NDX) on `d`.
- `symbols_for_bars(conn, d, grace_days=30) -> set[str]`: members on `d`, plus members that left within `grace_days` (so open positions keep a price), plus `BENCHMARK`.
- `all_symbols(conn, since) -> list[str]`: every symbol that was a member at any time after `since`, plus `BENCHMARK`, sorted.

### demo

Demo bars and FX rows look exactly like real ones, so the trigger is that a `runs` row with `is_demo` exists. While one exists, every row in the demo-owned tables is treated as demo data.

- `DEMO_TABLES = ("action_dismissals", "orders", "equity_snapshots", "paper_state", "book_positions", "book_targets", "book_fills", "book_trades", "news_vetoes", "bars", "fx_rates", "runs")`. `strategies` is kept on purpose. A purge also resets `strategies.paper_start` and `params` (the demo seed's paper clock; `RESET_PAPER_CLOCK`), so the first real `paper` run starts cleanly; `dividends` is never purged.
- `has_demo(conn) -> bool`
- `purge_demo(conn) -> bool`: `TRUNCATE <DEMO_TABLES> RESTART IDENTITY` when demo data exists. Does not commit.
- `purge_demo_if_needed(conn, dry_run) -> bool`: runs `purge_demo` in its own `db.transaction`. Under `dry_run` the purge runs, is rolled back and logs "would purge". The return value still says whether it purged or would have.

### sim (fill simulator, P2)

Pure and deterministic: no database, no network, no clock, no randomness, no logging. It imports only `seer_engine.dates` and `seer_engine.prices`, never `bars`, and `tests/test_sim_purity.py` checks in a subprocess that `psycopg`, `requests` and `yfinance` stay out of `sys.modules`. Every value is a frozen dataclass, and every function returns new values. All money and prices are `Decimal`, quantized to 4 dp half-up (`q`). Shares are `int`. A float or any other non-`Decimal` price raises `TypeError`. Import everything from `seer_engine.sim`.

**Rules** (design §5 + handover §3, all tested on synthetic bars):

| Topic | Rule |
|---|---|
| Fill | session `low < limit` (strict; a touch does not fill). Fill at the **open** if `open < limit`, else at the limit. Fill session = day 1 |
| Unfilled | the pending order expires at the end of its session; the slot is free for that night's picks |
| Session order | (1) time stop at the open, (2) gap at the open (`open <= SL` → `gap`, then `open >= TP` → `tp`), (3) intraday `low <= SL` → `sl` at SL, then `high > TP` → `tp` at TP (SL first), (4) fills, (5) expiries, (6) mark to close. A position filled today is not checked against TP/SL today |
| Time stop | `days_held >= 5` and a bar → exit at that bar's open, reason `time`, before any gap/TP/SL check |
| `days_held` | fill session = 1; +1 for every later session survived, bar or not. Intraday exit on day k records k; an exit at the open of day k (time, gap, gap-TP) records k − 1, so a time exit records 5 |
| Costs | `buy_cost = q(price × shares × 1.001)`, `sell_proceeds = q(price × shares × 0.999)`. Fill: `cash -= buy_cost`; exit: `cash += sell_proceeds` |
| `pnl_usd` | `sell_proceeds − buy_cost`, so Σ `pnl_usd` reconciles with cash exactly. Within 0.0001 of handover §3's `(exit − fill) × sh − 0.001 × (exit + fill) × sh` |
| Equity | `q(cash + Σ shares × last known close)` at each session's close. Pending orders reserve nothing in equity |
| Sizing | picks in rank order; each placed pick takes the lowest free slot. `budget = min(q(equity / 4), cash − Σ buy_cost(limit, shares) of pending orders)`, with `equity` the last snapshot. `shares = floor(budget / (limit × 1.001))`. Rejections: `held` (symbol has a live order, or a duplicate pick), then `no_slot`, then `lt_one_share`. A rejection never uses a slot. 0 picks is valid |
| Missing bar | an open position without a bar: no event, the day still counts, marked at the last close. A due time stop waits for the next bar's open. A pending order without a bar expires |
| Holidays | the caller steps NYSE sessions only (`dates.sessions`). `step` raises on a non-session |
| Splits | `apply_split` rewrites live orders in post-split units (see below) |

**Constants and helpers** (`sim.model`):
- `SLOTS = 4`, `TIME_STOP_DAYS = 5`, `COST_RATE = Decimal("0.001")`
- `OrderStatus = Literal["pending", "open", "closed", "expired"]`, `ExitReason = Literal["tp", "sl", "time", "gap"]`, `EventKind = Literal["fill", "expire", "exit", "split"]`
- `q(x) -> Decimal`: quantize to `PRICE_QUANTUM`, half-up.
- `buy_cost(price, shares)`, `sell_proceeds(price, shares) -> Decimal`: as in the table.
- `initial_cash_usd(idr, usd_idr) -> Decimal`: `q(idr / usd_idr)`, with `usd_idr` the IDR price of 1 USD on the start date.

**Values:**
- `Order(session_date, slot, symbol, last_price, limit_price, tp_price, sl_price, shares, status="pending", fill_date=None, fill_price=None, days_held=0, exit_date=None, exit_price=None, exit_reason=None, pnl_usd=None)`: mirrors the `orders` columns except `strategy_id`, `company`, `explanation`, `id` and `created_at`. It validates itself: `slot` is 1–4, `shares >= 1`, `sl < tp`, the fill fields exactly when `open`/`closed`, and the exit fields exactly when `closed`.
- `Portfolio(cash, equity, orders=(), marks=(), last_session=None)`: one strategy's state between sessions.
  - `orders` holds **live** orders only (pending + open), sorted by slot, at most one per slot and one per symbol.
  - `marks` is `(symbol, last close)` for exactly the open symbols, sorted.
  - `equity` is the last snapshot's (or the initial cash).
  - Methods: `open_orders()`, `pending_orders()`, `free_slots()` (ascending), `held_symbols()` (all live, sorted), `mark(symbol)`.
- `new_portfolio(cash_usd) -> Portfolio`: `cash = equity = q(cash_usd)`.
- `Event(session_date, kind, order, forced=False, cash_usd=None)`:
  - `order` is the order state after the event. A terminal order (closed or expired) leaves the portfolio and appears only here, which is where P4 writes it.
  - `cash_usd` is the cash moved: `-buy_cost` on a fill, `+proceeds` on an exit, cash in lieu on a split, and `None` on an expire.
  - `forced=True` marks an exit made without a bar (`close_unpriced`, or a split that floors an open position to 0 shares).
- `Snapshot(date, cash_usd, equity_usd)`: one `equity_snapshots` row.
- `StepResult(portfolio, events, snapshot)`.

**Functions:**
- `step(portfolio, session_date, bars: Mapping[str, Bar]) -> StepResult` (`sim.lifecycle`): advances through one session.
  - `bars` holds split-adjusted bars keyed by symbol. Only bars for symbols with a live order are read and validated; the rest are ignored. A symbol absent from `bars` has no bar this session.
  - **Event order:** all exits in slot order, then all fills in slot order, then all expiries in slot order.
  - Raises `ValueError` when `session_date` is not an NYSE session, is not after `last_session`, or differs from a pending order's `session_date`, or when a bar has the wrong symbol or date. Raises `TypeError` on a non-`Bar` or a non-`Decimal` price.
- `close_unpriced(portfolio, symbols) -> (Portfolio, events)` (`sim.lifecycle`): force-closes open positions that will never get another bar (delisted, halted for good). Each exits at its mark, reason `time`, `exit_date = last_session`, with `forced=True`. It recomputes `equity`, so persist the snapshot after it. The caller decides that no bar will come; a pure step cannot know.
- `Pick(symbol, last_price, limit_price, tp_price, sl_price)` (`sim.sizing`): one ranked pick before sizing. It requires `sl < limit < tp`.
- `size_picks(portfolio, picks, session_date) -> SizingResult(portfolio, placed, rejected)` (`sim.sizing`): sizes the picks for the next session.
  - `placed: tuple[Order, ...]` and `rejected: tuple[Rejection(symbol, reason), ...]` are in pick order. `RejectReason = Literal["no_slot", "held", "lt_one_share"]`.
  - Cash does not change; a pending order pays at its fill.
  - Raises `ValueError` when `session_date` is not a session after `last_session`, or when a pending order for another session is still in the portfolio (step that session first).
- `apply_split(portfolio, symbol, factor, session_date) -> (Portfolio, events)` (`sim.split_adjust`):
  - `factor = split_to / split_from`, the same number as `splits.Split.factor`. 10 is a 10-for-1; `Decimal(1) / 32` is a 1-for-32 reverse split.
  - Call it once per split, after session S−1's `step` and before stepping the execution session S, with `session_date = S`.
  - Prices become `q(p / factor)`, and `shares = floor(shares × factor)`. The open position's fractional remainder is paid as cash in lieu at the adjusted mark, with no cost and outside `pnl_usd`; the amount is on the `split` event's `cash_usd`.
  - A pending order that floors to 0 shares emits `expire`. An open position that floors to 0 is paid out in lieu, emitting a forced `exit` (reason `time`, `pnl_usd = in lieu − buy_cost`).
  - Events are in slot order. `equity` stays at the last snapshot until the next `step` (unlike `close_unpriced`, which recomputes it). The caller applies each split exactly once (`split_adjustments` guarantees this).
  - Raises `ValueError` when a rescaled price or mark rounds to 0 at 4 dp, or SL rounds up to TP, and leaves the input untouched. Real listed stocks never get there.
  - P3 does not need it: backfilled history is already adjusted backwards.

**Determinism:** the same inputs give `==` and `repr`-identical events and snapshots. The insertion order of `bars` does not matter. `tests/test_sim_scenario.py` checks this, and also holds the 12-session hand-checked scenario.

### strategies (P3)

Pure, like `sim`: no database, network, clock, randomness or logging, and never `bars`.
`tests/test_strategy_purity.py` globs every module in `strategies/`, `backtest/`,
`fundamentals/` and `paper/` — the two declared impure edges `backtest/io.py` and
`paper/store.py` excepted — and checks this in a subprocess and on the AST. P4 calls this code nightly and P6 adds strategies B and C beside `a.py`.

**`strategies.base`**
- `@dataclass(frozen, slots) History(symbol, dates, open, high, low, close, volume)`: one symbol's
  daily bars, ascending, one row per bar it has (gaps allowed). `dates` is `datetime64[D]`; the
  rest are float64 arrays of the same length. `len(h)`, `h.upto(d)` (bars dated `<= d`, a view),
  `h.last_date()`, `h.index_of(d)` (row of the bar dated `d`, else `None`).
- `history_from_bars(symbol, bars: Sequence[Bar]) -> History`: `float(Decimal)` per field.
- `Strategy` protocol: `id: str`, `lookback: int` (bars per symbol `picks` needs), and
  - `picks(history, members, data_date, params) -> list[Pick]`: the nightly entry point. `history`
    maps symbol → `History` through `data_date`; longer histories are fine, only the last
    `lookback` bars dated `<= data_date` are read.
  - `prepare(history) -> Any` and `picks_prepared(prepared, members, data_date, params)`: the
    backtest's fast path, computing parameter-independent features once for every date.
  - **Contract:** `picks_prepared(prepare(H), M, d, p) == picks({s: h.upto(d)}, M, d, p)` for
    every `d`. A test proves it on a multi-symbol synthetic set.

**`strategies.indicators`** — window functions take 2-D float64 arrays shaped `(rows, W)`, oldest
column first, and return one float64 per row, `NaN` when `W` is too short. They use only
elementwise numpy and an explicit loop over columns (never a reduction along time), so a row's
result is bit-identical whatever the number of rows.
- `sma_window(close, n)`: the last `n` closes summed left to right, `/ n`.
- `wilder_rsi_window(close, n)`: changes `d_i = c_i − c_{i−1}`; seed = mean of the first `n` gains
  and losses; then `avg = (avg·(n−1) + x) / n`; `100` when the average loss is 0, else
  `100 − 100 / (1 + avgG/avgL)`.
- `wilder_atr_window(high, low, close, n)`: `TR = max(h − l, |h − c_prev|, |l − c_prev|)` from the
  window's second bar; seed = mean of the first `n` TRs; Wilder after.
- `mean_dollar_volume_window(close, volume, n)`: mean of `close × volume` over the last `n` bars.
- `mean_window(x, n)`: mean of the last `n` columns of any series, summed left to right, `/ n` (Strategy B: volume).
- `stdev_return_window(close, n)`: population (ddof 0) stdev of the last `n` one-bar returns `c_i / c_{i−1} − 1`; `NaN` when `W < n + 1`.
- `rolling(fn, *series, window, **kw)`: a length-T series → length-T result via
  `sliding_window_view`, `NaN` for `t < window − 1`.

**`strategies.a`** (design §4)
- `LOOKBACK = 200`, `SMA_N = 200`, `RSI_N = 2`, `ATR_N = 14`, `DV_N = 20`.
- `@dataclass(frozen, slots) AParams(rsi_max=10.0, limit_atr=Decimal("0.5"), tp_atr=Decimal("1.0"), sl_atr=Decimal("1.5"), min_dollar_volume=20_000_000.0)`;
  `as_dict() -> dict[str, str]` in a stable key order (what P4 writes to `strategies.params`).
- `DESIGN_PARAMS = AParams()`: design §4's starting values, the selection fallback.
- `STRATEGY_A_PARAMS`: **the frozen parameters**: `{"rsi_max": "10", "limit_atr": "0.5", "tp_atr": "1", "sl_atr": "1.5", "min_dollar_volume": "20000000"}`,
  selected on the in-sample window only by the committed report `docs/backtests/2026-10-02-strategy-a.md`
  (no grid run qualified, so these are the design values, written as an explicit literal).
  `tests/test_strategy_a_frozen.py` fails if code and report disagree. Changing a value means
  re-running the backtest and committing its report, and it resets the forward clock.
- `features_at(history, data_date) -> list[Features]` (sorted by symbol) and
  `picks_from_features(features, members, params) -> list[Pick]`; `StrategyA` implements
  `Strategy` with `id = "A"`, `lookback = LOOKBACK`; `STRATEGY_A = StrategyA()`.

| Rule | Strategy A |
|---|---|
| Timing | Picks for session S use bars through `data_date = prev_session(S)` only; `last_price` = that close. Every indicator is a function of the symbol's last 200 bars ending at `data_date`, Wilder recursions seeded inside that window, so the backtest and the nightly job compute bit-identical floats |
| Eligible | member on `data_date` (point-in-time), a bar dated `data_date`, ≥ 200 bars through it |
| Setup | `close > SMA200` and `RSI(2) < rsi_max` and 20-day mean `close × volume > min_dollar_volume`, all strict |
| Prices | `last = to_decimal(close)`, `atr = to_decimal(ATR14)`, `limit = q(last − limit_atr·atr)`, `tp = q(limit + tp_atr·atr)`, `sl = q(limit − sl_atr·atr)` |
| Dropped | after `q`: `last ≤ 0`, `limit ≤ 0`, `sl ≤ 0`, `sl ≥ limit` or `tp ≤ limit` (`Pick` would raise); dropped silently, never raised |
| Ranking | `(rsi, symbol)` ascending; every qualifying candidate is returned. Held symbols are not filtered: `size_picks` rejects them as `held` without using a slot |

**Float vs Decimal.** Indicators and the setup comparisons are float64; everything handed to the
simulator is a 4-dp `Decimal`. `bars.close` is `numeric(12,4)` (at most 12 significant digits), so
`to_decimal(float(close))` round-trips exactly through `repr`. A float could flip a strict
threshold only within about 1e-12 of it (RSI exactly 10.0 is excluded by `<`), and because the
window math is bit-identical, it flips the same way in the backtest and nightly.

**`strategies.a2`** (P3b: the Strategy A rework, `docs/handover/2026-10-03-strategy-a-rework.md`)

Strategy A2 is Strategy A plus four pre-registered variants, fixed before any result was seen. It
reuses `a.py`'s features, setup and bracket helpers unchanged. `a.py` and `STRATEGY_A_PARAMS` are
v1's record and do not move.

- `REGIME_SYMBOL = "SPY"`. It equals `universe.BENCHMARK`, which a test asserts. `a2` cannot
  import `universe`, because that imports psycopg.
- `FLOOR_PRICE = 10.0`.
- `VARIANTS = ("control", "regime", "regime_calm", "regime_calm_floor")`, which is V0–V3, in this
  order everywhere.
- `@dataclass(frozen, slots) A2Params(variant="control", rsi_max=10.0, limit_atr=Decimal("0.5"), tp_atr=Decimal("1.0"), sl_atr=Decimal("1.5"), min_dollar_volume=20_000_000.0)`:
  - A's five fields, validated and coerced exactly as `AParams`; an unknown variant is a
    `ValueError`.
  - `a_params()` gives the `AParams` of the same five values.
  - `as_dict()` puts `variant` first, then `AParams.as_dict()`. This is what P4 would write to
    `strategies.params`.
  - `A2Params.from_a(variant, p)`.
- `A2_DESIGN_PARAMS = A2Params()`: V0 with the design values, the walk-forward fallback.
- `STRATEGY_A2_PARAMS = None`.
  - The P3b gate failed (`docs/backtests/2026-10-02-strategy-a2-walkforward.md`), so nothing is frozen
    and A2 may not be deployed.
  - `tests/test_strategy_a2_frozen.py` fails if a value appears without a passing report.
- `regime_on(spy, data_date) -> bool`, `picks_from_features_a2(features, members, params, regime)`.
- `A2Prepared` / `prepare_a2(history)`: `prepare_a`'s columns plus SPY's regime column, computed
  once.
- `picks_prepared_a2(...)`.
- `StrategyA2` implements `Strategy` with `id = "A2"`, `lookback = LOOKBACK`; `STRATEGY_A2 = StrategyA2()`.

| Variant | Rule on top of Strategy A |
|---|---|
| V0 `control` | none: its picks `==` `STRATEGY_A.picks` for the same five params (tested) |
| V1 `regime` | no new picks on a `data_date` where SPY's close ≤ SPY's SMA(200). The rule is strict `>`, so equality means off. It is also off when SPY has no bar on `data_date` or fewer than 200 bars through it. The SMA is `sma_window` over SPY's last 200 closes ending at `data_date`, bit-identical between `picks` and `prepare` |
| V2 `regime_calm` | V1, ranked by `(ATR(14) / close, RSI(2), symbol)` ascending instead of `(RSI(2), symbol)` |
| V3 `regime_calm_floor` | V2, plus `close ≥ 10.00` (inclusive; fixed, never tuned) |

SPY is read from the same `history` mapping as the members, never from `members`. It can never be a
pick: it is excluded explicitly, and the universe never lists it. The P4 identity
(`picks_prepared(prepare(H)) == picks(upto(d))`) and no look-ahead hold for every variant,
including SPY's own bars dated ≥ S.

**`strategies.b_model`** (P6a: `docs/handover/2026-10-03-strategy-b-ranker.md`)

This is the one place scikit-learn is used. It is pure: no I/O, no clock and no global randomness,
because seeds are passed as `random_state=0`.

- `TREE = "tree"` and `RIDGE = "ridge"`. `TREE_PARAMS` is the pre-registered
  `HistGradientBoostingRegressor(loss="squared_error", learning_rate=0.05, max_iter=300, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0, early_stopping=False, random_state=0)`.
  There is no hyperparameter search. `RIDGE_ALPHA = 1.0`.
- `BModel(kind, n_features, digest, estimator)`. Equality and hash are `(kind, n_features, digest)`.
  `digest` is the sha256 of the tree's baseline and node arrays, or of the ridge coefficients and
  intercept. `predict(X)` is bit-identical per row, whatever the batch size.
- `fit_tree(X, y, *, threads=None)` and `fit_ridge(X, y, alpha=RIDGE_ALPHA)`. The ridge is closed
  form with an unpenalized intercept, accumulated in fixed `BLOCK_ROWS` blocks, so it never depends
  on BLAS threads. `fit(kind, X, y)` dispatches between them.
- `importance(model, X)`: shares that sum to 1. Trees use split gain; ridge uses |coef| × the
  feature's std. `r2(y, pred)`.
- `dumps(model) -> bytes` (a protocol-5 pickle of `(kind, n_features, estimator)`),
  `loads(data) -> BModel` (it recomputes the digest) and `sha256(data) -> str`. An artifact's
  identity is `sha256(file bytes)` and `loads(bytes).digest`; never re-pickle a loaded tree to
  compare bytes, since the pickle framing can differ.

**`strategies.b`** (P6a: Strategy B, the ML cross-sectional ranker)

Strategy B ranks the same eligible set as A by a learned prediction of each order's net return, and
keeps A's fixed bracket. `a.py` and `a2.py` are not changed.

- `LOOKBACK = 200`, `SPY_SYMBOL = "SPY"` (equal to `universe.BENCHMARK`, which a test asserts), and
  `MIN_DOLLAR_VOLUME = 20_000_000.0` (A's floor, strict `>`).
- `FEATURE_NAMES`: the 15 `SYMBOL_FEATURES` (returns over 1/5/20/60/120 bars, close ÷ SMA(50) − 1,
  close ÷ SMA(200) − 1, RSI(2), RSI(14), ATR(14) ÷ close, the 20-bar stdev of returns, 20-day mean
  dollar volume, 5- ÷ 20-day mean volume, gap and range position), then the 3 `SPY_FEATURES` (SPY's
  5- and 20-bar returns and close ÷ SMA(200) − 1).
  - Each symbol feature is turned into a cross-sectional rank in [0, 1] among that date's
    candidates only (`rank01`: ties averaged, 0.5 for a single candidate). The SPY features stay
    raw.
  - Ranking dollar volume itself equals ranking its log (D6).
- **Candidates on `d`:** a member other than SPY, with a bar dated `d`, at least 200 bars through
  `d`, a 20-day mean dollar volume above $20M and all 15 raw features finite. SPY's features must
  also be defined on `d`; if they are not, there are no candidates. Bracket validity is not a
  candidate rule: it applies to picks and to training rows.
- `Design(data_date, symbols, X, close, atr)`, `BPrepared` / `prepare_b(history)` (raw window
  features once per (symbol, date)), `BPrepared.design_on(members, d)`, and `design_at(history, members, d)`
  (the single-window path, bit-identical to `prepare_b`).
- `BParams(model)`. Any `Predictor` with `predict(X) -> float64` fits, and `b_model.BModel` is the
  real one. `bracket(symbol, close, atr)` is `a._bracket` at the design values.
  `picks_from_design(design, params)` keeps predictions > 0.0, ordered by (−prediction, symbol).
- `FrozenModel(report, artifact, train_end, sha256)`.
- `STRATEGY_B_FROZEN = None`.
  - The P6a gate failed (`docs/backtests/2026-10-02-strategy-b-walkforward.md`), so nothing is frozen, no artifact is committed, and B may not be deployed.
  - `tests/test_strategy_b_frozen.py` fails if a value or an artifact appears without a passing report. It reads the constant as `seer_engine.strategies.b.STRATEGY_B_FROZEN` at call time; the package does not re-export it.
- `StrategyB` implements `Strategy` with `id = "B"` and `lookback = LOOKBACK`; `STRATEGY_B =
  StrategyB()`. Its contract is `picks_prepared(prepare(H), M, d, p) == picks({s: h.upto(d)}, M, d,
  p)` for every model, and no look-ahead, SPY's bars included. B-linear is the same `STRATEGY_B`
  with a ridge `BParams`.

### strategies.c (P6, Strategy C)

Pure like the rest of `strategies/` (the purity tests cover it): no psycopg, requests, clock,
randomness, logging or `fromtimestamp`. The network half lives in `finnhub.py`, `llm.py` and
`commands/veto.py`.

- `PROMPT_VERSION = "c-veto-v1"`, `FROZEN_MODEL = "glm-5.3"`, `STRATEGY_C_ID = "C-news-veto"` (the object id in C's spec; the roster id is `C`). `Verdict = Literal["allow", "veto", "failed"]`, `VERDICTS`.
- `Headline(id, published, source, headline, summary)`: one Finnhub news item as C reads it; `published` is tz-aware UTC.
- `CParams(a=STRATEGY_A_PARAMS, max_candidates=10, news_days=3, max_headlines=20, max_summary_chars=280, earnings_sessions=5, model=FROZEN_MODEL, prompt_version=PROMPT_VERSION, temperature="0", thinking="disabled", max_tokens=1024)`; `as_dict()` gives every key as a plain string: A's params as `a.<key>`, `a_object`, `a_object_id`, the fields above, and the full `system_prompt` and `user_template` texts, so C's digest moves if any of them changes. `STRATEGY_C_PARAMS = CParams()`.
- `SYSTEM_PROMPT`, `USER_TEMPLATE`: the frozen `c-veto-v1` texts (the plan's K1, verbatim). The system prompt lists what is a veto (earnings inside the holding window or in the last 3 days; guidance cut, warning or large miss; accounting problems or fraud; a lawsuit, regulatory action, investigation or recall; M&A, spin-off or tender news; a halt, delisting, bankruptcy or going-concern doubt; a major analyst or credit downgrade; the CEO or CFO leaving) and asks for one JSON object `{"verdict": "allow" | "veto", "reason": "<one sentence>"}`.
- `candidates(history, members, data_date, params)` / `candidates_prepared(prepared, members, data_date, params)`: `STRATEGY_A.picks(...)` / `picks_prepared(...)` with `params.a`, cut to `params.max_candidates`. The one place C's candidates are computed (`veto` and `NewsVeto` both call it).
- `NewsVeto(allowed: Mapping[date, frozenset[str]], id=STRATEGY_C_ID, lookback=STRATEGY_A.lookback)` implements `Strategy`: `picks` keeps the candidates whose symbol is in `allowed[next_session(data_date)]`, in rank order; `prepare` is A's; `picks_prepared` is the same filter on `candidates_prepared`. `with_allowed(allowed)` returns a copy carrying stored verdicts. `STRATEGY_C = NewsVeto(allowed={})` (with no verdicts it never buys).
- `news_dates(started_at, days) -> (from, to)`: ET calendar dates for Finnhub; `to` is `started_at` in New York.
- `earnings_window(session, n) -> (session, the n-th session counting session as 1)`.
- `select_headlines(items, cutoff, cap)`: items published strictly before `cutoff`, newest first (ties: higher id first), at most `cap`.
- `user_prompt(symbol, session, window_end, earnings, cutoff, headlines, params) -> str`: `USER_TEMPLATE` filled; summaries cut to `max_summary_chars` at a word boundary; `No headlines.` when there are none.
- `parse_verdict(text) -> (verdict, reason)`: accepts surrounding whitespace and a fenced JSON block, takes the first `{...}` object; the verdict must be exactly `allow` or `veto` (case-insensitive) and the reason a non-empty string (whitespace collapsed, at most 300 characters). Anything else is `("failed", "unparsable reply: <first 120 chars>")`.
- `allowed_map(rows) -> {session: frozenset of allowed symbols}` from `(session, symbol, verdict)` rows.

### backtest (P3)

Every module except `io.py` is pure (same purity test as `strategies`). Nothing here writes to
the database.

- **`backtest.market`**: `Membership(intervals)` with `members_on(d) -> frozenset[str]` (both
  indices unioned, `[start, end)`), evaluated in memory instead of one query per date.
  `Market(history, membership, fx, fundamentals=EMPTY_FUNDAMENTALS)`: `bar(symbol, d) -> Bar | None`
  builds a 4-dp `Decimal` `Bar` on demand (only for symbols with a live order, and SPY),
  `bars_on(d, symbols)`, `last_bar_date(symbol)`, `usd_idr_on(d)` (latest FX row dated `<= d`,
  `ValueError` when none), `spy()`.
  **`fundamentals`** (edgar-fundamentals) is the point-in-time SEC fact panel
  (`fundamentals.FundamentalPanel`), read through `panel.as_of(symbol, t)`. It defaults to
  `EMPTY_FUNDAMENTALS`, which **is** `fundamentals.EMPTY_PANEL` — one shared instance, so
  `market.fundamentals is EMPTY_PANEL` is a usable identity test — so every existing
  `Market(...)` call site keeps working unchanged. `Market` is frozen, so
  `with_fundamentals(panel) -> Market` is the supported way to attach a panel to a market built
  without one (the research store, a paper replay, a test fixture) without any caller knowing the
  field order. The panel is deliberately **independent of `history`**: a symbol may have facts and
  no bars (a delisted ever-member) or bars and no facts (every ETF), and nothing cross-checks the
  two. `__post_init__` type-checks it like the other fields.
  **`series`** (eodhd-survivorship-market phase 3) is a `MarketSeries`: market-wide daily series by
  name (`VIX`, `VIX3M`, `VIX9D`, `VVIX`, `VXN`, `T13W`, `T5Y`, `T10Y`, `T30Y`, `GOLD`), each
  `(date, float)` strictly ascending and finite, in the unit an allocator reasons in (the VIX family
  in points, yields in percent, gold in USD/oz). Every read takes the allocator's `data_date` and
  sees only rows dated on or before it: `value_on(name, data_date)` is the **latest** value on or
  before it (a Treasury index has no close on Columbus Day; the last published yield is what a
  trader knew), `upto(name, data_date, *, last=None)` the rows up to it (the final `last` only),
  `names()` the non-empty series, `first_date(name)`. It defaults to `EMPTY_SERIES` (one shared
  instance); only `research.load_store` fills it, from `market_series.csv`, and
  `with_series(series) -> Market` attaches one. An allocator that reads it declares
  `market_fields = ("series",)`, and `lab.runner.preflight_data` refuses such a method on a store
  whose `len(market.series) == 0` before anything is spent.
- **`backtest.runner`**: `INITIAL_IDR = Decimal("10000000")` — the owner's real Gotrade capital, the
  same number `paper.capital.PAPER_INITIAL_IDR` holds. It was 20,000,000 while every simulated fee
  was a flat percentage, where only ratios matter; Gotrade's measured schedule has a $0.10
  per-order floor, so the rate depends on the slot (at 17,841 IDR/USD over 20 names a 10M book pays
  1.035% round trip and a 20M book 0.660%) and a 20M lump would price a cheaper world than the owner
  lives in. Because it changed once, it is not the capital of a recorded trial: a trial's capital
  is its `trial_provenance.initial_idr`, and every path that re-runs or de-funds a recorded trial
  reads that (`lab.runner.recorded_capital`). `INITIAL_IDR` is only the default for a new run.
  `run_backtest(market, strategy, params, start, end, *, prepared=None, initial_idr=INITIAL_IDR, contributions=None, rules=DESIGN_V0) -> RunResult`
  is the "P3 backtest loop" below: each session `size_picks(picks(prev_session(S)))` → `step` →
  `close_unpriced` for held symbols whose bars ended for good (`last_bar_date < S`; a halt whose
  bars resume is left to the simulator's missing-bar rule). `RunResult` holds `snapshots`
  (`[0] = Snapshot(prev_session(start), cash0, cash0)`, then one per session), `events`, `closed`,
  `open_at_end` (marked at the last close, never liquidated) and rejection counts.
  `rules` prices every buy, fill and exit — `DESIGN_V0` (the default) is the flat 0.1% a side every
  closed §5 record was run at, `DESIGN_V0_GOTRADE` Gotrade's measured schedule including its $0.10
  per-order minimum — and is passed straight to `sim.size_picks`, `sim.step` and
  `sim.close_unpriced`; `run_rules` dispatches a `"bracket"` rule set here (`sim.rules.is_bracket`)
  rather than to the book engine.
  `contributions` is a `sim.contributions.Contributions` or None (the default, and every closed
  record) — either the owner's `ContributionSchedule`, whose calendar dates are credited at the open
  of the first NYSE session on or after each of them and converted at this run's single rate, or a
  **record** of `(session, usd)` deposits already made and already converted, which are credited
  unchanged (that is what a paper replay passes, so it reproduces the dollars the night wrote). A
  credit raises cash **and** equity before that session sizes anything, and `RunResult` records what
  it was funded with plus `cashflows` — `(session, usd)` per credited deposit, the dated series a
  money-weighted return is computed from. A deposit is money arriving, never a return.
  `survivorship(market, start, end) -> tuple[YearGap, ...]`: per year, the (member, session) pairs
  with no bar, split into never-fetched symbols and other gaps.
- **`backtest.benchmark`**: `parse_dividends(text)`, `buy_and_hold(spy, start, end, initial_cash, *, dividends=(), name)`
  and `spy_curves(...) -> (price, total_return)`. Whole shares at the first session's open after
  the 0.1% cost, idle remainder, marked at each close, never sold. Total-return reinvests a
  dividend when `start < ex_date ≤ end`: cash `+= q(shares × amount)`, then whole shares at that
  close with `buy_cost`.
  `buy_and_hold(..., cost_model="flat")` and `spy_curves(..., *, cost_model="flat")` (Sean phase 6):
  under `"gotrade"` every buy (the first one and each dividend reinvestment, whole or fractional)
  pays `sim.costs.gotrade_cash` instead of 0.1%, with the share count from
  `sim.costs.gotrade_shares_for` (the most whose rounded cash fits). Any other value is a
  `ValueError`. `"flat"` leaves every curve unchanged. The paper benchmark
  (`paper/benchmark.py`) can be asked for the same two models since the fee rebuild's phase 3,
  but nothing passes it `"gotrade"` yet, so every live paper night is still flat.
- **`backtest.metrics`**: `strategy_metrics(snaps, pnls, cashflows=()) -> Metrics` and
  `checklist(m, spy_return)`,
  identical to `web/lib/metrics.ts` (a loss is `pnl ≤ 0`; PF = gross win / gross loss, `inf` with
  no loss; max drawdown on per-session equity; total return = last / first − 1;
  months = days / 30.44). Adds CAGR, average `days_held` and the exit-reason breakdown.
  `run_metrics(RunResult)`, `curve_metrics(BenchmarkCurve)`. `tests/test_backtest_metrics.py`
  replays every case in `web/lib/metrics.test.ts`.
  A run that received deposits departs from that parity in exactly one place, and the asymmetry is
  the point (lab-realistic-gate R2). `max_drawdown` is then measured on the **time-weighted wealth
  index** — the curve the strategy would have traced on one unchanging dollar, chained from the
  same `cur / (prev + flow_t) - 1` session growth `book_runner._daily_returns` uses — because a
  deposit raises the peak and refills the trough, so raw equity reads *safer* than the strategy
  was, and the drawdown is a go-live condition (`tuning.MAX_DRAWDOWN`, re-derived by
  `lab.store.owner_failures`). Measured on the smoke fixture: 7.96% on raw equity against 10.55%
  honest, with the DCA'd SPY benchmark damped from 25.75% to 10.59%. `total_return` and `cagr` are
  *not* corrected, deliberately: they are the recorded shape of the curve that readers of the 128
  historical trials depend on, and `mwr` (`money_weighted_return`, None exactly when the run
  received no deposit) stands beside them as the number that answers what the money earned. The
  drawdown has no such companion, which is why it is the one that moves. `external_cashflows(r)`
  reads a result's deposits as `(session, usd)` pairs and `flow_map(cashflows)` is the shared
  `{session: total deposited that session}` lookup, summing rather than overwriting when the
  calendar lags two deposits onto one open. With no cashflows every expression above takes its
  original form verbatim, so an unfunded run is byte-identical.
- **`backtest.tuning`**: `IS_START = 2015-10-19` (the first session with 200 bars of history behind
  its `data_date`), `OOS_START = 2022-01-03` (in-sample ends 2021-12-31). `grid()`: the 81 params
  fixed before any result was seen — RSI `{5, 10, 15}` × limit `{0.25, 0.5, 0.75}` × TP
  `{0.75, 1.0, 1.5}` × SL `{1.0, 1.5, 2.0}` ATR. `select(rows)`: highest in-sample total return
  among runs with max DD ≤ 20% and PF ≥ 1.3; ties → lower max DD → earlier grid index;
  `DESIGN_PARAMS` when none qualifies. `gate(oos, spy_tr_oos) -> Verdict`: passes only when, on
  **out-of-sample**, total return > total-return SPY, PF ≥ 1.3 and max DD ≤ 20%.
- **`backtest.report`**: `BacktestReport`, `render_markdown`, `equity_csv`, `equity_svg`,
  `report_stem(data_end)`. Deterministic: the same inputs give byte-identical files. The Markdown
  carries two machine-readable lines, `frozen-params:` (the code's `STRATEGY_A_PARAMS` at run
  time) and `selected-params:` (the in-sample selection), which `test_strategy_a_frozen.py` reads
  with `parse_params_line`.
- **`backtest.io`** (impure): `load_market(conn, *, cache_dir=CACHE_DIR, refresh=False) -> (Market, bars_rows)`,
  `read_dividends(path=DIVIDENDS_CSV)`, `write_report(out_dir, report) -> list[Path]`,
  `write_wf_report(out_dir, report: WalkForwardReport) -> list[Path]` (renders all five files,
  `<stem>.md`, `-equity.csv`, `-equity.svg`, `-variants.svg`, `-grid.csv`, before writing any, LF
  endings; returns the paths in that order).
- **`backtest.io`, the fundamentals load** (edgar-fundamentals; still the only impure module here):
  `load_market` now also fills `market.fundamentals` via
  `load_panel(conn, *, cache_dir=CACHE_DIR, refresh=False) -> Panel`, inside the same
  `REPEATABLE READ, READ ONLY` transaction it already owns and rolls back.
  - The rows come from `fundamental_facts` JOINed to `ticker_cik`, because the facts are
    **CIK-keyed** and the panel is **symbol-keyed**.
  - It is cached by table fingerprint exactly the way `bars` is:
    `facts_fingerprint(conn) -> (count(*), max(filed))` **over the join** is the cache key,
    `facts_cache_path` names `fundamentals-<max filed>-<rows>.pkl` in `.cache/`, and
    `read_facts_frame` streams one COPY on a miss (or with `refresh`). A broken pickle is a
    warning and a re-download, never fatal.
  - **It degrades instead of failing.** `facts_fingerprint` tests both tables with `to_regclass`
    and returns `(0, None)` when **either** is missing, so `load_panel` returns
    `EMPTY_FUNDAMENTALS` with no error — the state of every database that has not run
    `005_fundamentals.sql`, and of one that has but has not yet run `fundamentals`. `load_market`
    against such a database is unchanged (verified against the live Neon DB, and the backtest and
    `load_market` output are byte-identical to `origin/main`).
  - `read_facts(*, conninfo=None) -> tuple[Fact, ...]` opens its own connection
    (`DATABASE_URL_UNPOOLED`), runs the same fingerprint + COPY + `facts_from_frame` trio
    `load_panel` uses — so the facts equal the panel's by construction — and always rolls back.
    It lives **here, not in `commands/research_store.py`**: `io.py` is the one module in
    `seer_engine.backtest` that touches the database and the one `test_strategy_purity.py` skips
    by name, and `test_research_store.py::test_no_neon_and_no_database_url_needed` AST-scans both
    `research.py` and the `research_store` command and fails either one that names
    `seer_engine.db` or `psycopg`. The "Never Neon" invariant is untouched: `research.py` still
    imports nothing from `seer_engine.db`, and `build_store` still takes a plain sequence of facts.
  - `tests/test_market_fundamentals.py` covers the field, the `EMPTY_PANEL` identity, the
    `with_fundamentals` / `replace` carry-through, the `to_regclass` degradation path and the fact
    cache.

**Windows.** In-sample 2015-10-19 → 2021-12-31 (tuning); out-of-sample 2022-01-03 → the last SPY
bar (validation, run once); full 2015-10-19 → the last SPY bar (one continuous portfolio). Each
window starts its own 20,000,000 IDR portfolio at the FX rate on or before its first session, and
its own two SPY curves on the same session.

**The report** (`docs/backtests/<data end>-strategy-a.md`): data inventory; the in-sample grid,
all 81 rows; the selection and why; in-sample, out-of-sample and full-window results each against
price-only and total-return SPY (total return, CAGR, win rate, PF, max DD, trades, average days
held, exit reasons, go-live checklist); the survivorship note with per-year missing
(member, session) counts; the gate verdict in one sentence. `-equity.csv` is wide (`date` + one
column per curve) and `-equity.svg` is a hand-written chart, no plotting dependency.

**Committed result** (2026-10-02 data): gate **FAILED**. Strategy A fails the P3 gate: out of sample it returned −15.0% against +71.9% for total-return SPY, with profit factor 0.92 and max drawdown 33.3%, so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; P4 must not start until Strategy A is reworked.
See `docs/backtests/2026-10-02-strategy-a.md`.

**Survivorship.** 115 index members in the full window have no bars at all (delisted or
acquired; Yahoo no longer serves them), so the backtest cannot trade them (115 is the report's
"Index members in the window with no bars at all"). A dip-buying strategy is exactly what those
collapses would have hurt, so the result is biased in Strategy A's favour; the report counts the
gap per year.

**Design §14 does not cover this.** The delisting stress test (delisting-stress-roster-rules) found no break-even for the four quant roster entries even at a total wipeout — but it ran on the **dev window (1996-01-02 → 2015-10-16)**, against the research store's own membership, on the F-family book strategies. This gate is Strategy A, a rule, on Neon bars from 2015-10-19 — a different strategy, a different window and a different data source. Its 115 unserved members are not the store's 404 in-window exits, and nothing measured there transfers to a dip-buying rule here. The harness could be pointed at this window, and has not been. Until it is, this gap stays **unquantified** — §14's number must not be read across.

### backtest walk-forward (P3b)

This adds to P3 without changing it. Every v1 call takes its unchanged code path, and the
committed v1 report re-renders byte-identically on its own data (checked by re-running `backtest` on the unchanged Neon data (2026-10-02, 1,817,429 bar rows)). Like
the rest of `backtest/`, every module here except `io.py` is pure, and the purity glob covers it.

- **`backtest.runner.ParamsSchedule(segments)`**: `segments` is `((first_session, params), ...)`,
  NYSE sessions, strictly ascending, at least one. `at(session)` gives the params of the last
  segment starting on or before `session`, and raises `ValueError` before the first.
  `run_backtest(..., params=<ParamsSchedule>, ...)` picks for session S with `params.at(S)` (S is
  the session traded, not `data_date`), and raises `ValueError` if `start` is before the first
  segment. Orders keep the bracket they were placed with across a switch. With any other `params`,
  `run_backtest` behaves exactly as in P3.
- **`backtest.metrics.metrics_through(r, end)`**: `run_metrics` of `r` cut at session `end`, using
  snapshots dated `<= end` and exits on or before `end`. **Prefix property:** it equals
  `run_metrics` of the same run with `end=end`, which tests prove on the scenario market and a
  Strategy A market.
- **`backtest.tuning.select(rows, *, fallback=DESIGN_PARAMS)`**: P3's rule, tie-breaks and reason
  strings, with the none-qualifies params as an argument. Without it, it behaves exactly as in P3.
- **`backtest.walkforward`**:
  - `FIRST_TRADE_YEAR = 2018`, `SEEN_BEFORE_START = tuning.OOS_START` (2022-01-03, the burned P3
    out-of-sample start), `COMBINED = "walk-forward"`.
  - `Fold(year, tune_start, tune_end, trade_start, trade_end)` and
    `folds(is_start, first_year, end)`.
  - `combinations()`: 324 `A2Params`, variant outer, grid inner.
  - `tune(market, strategy, prepared, combos, folds)`: one run per combination, and per fold a
    `GridRow` via `metrics_through(run, fold.tune_end)`. Sequential, in combination order.
  - `select_fold(rows, variant=None)`. The combined selection falls back to `A2_DESIGN_PARAMS`; a
    variant's own falls back to `A2Params(variant=v)`.
  - `schedule(folds, selections)`, then `walk_forward(...) -> WalkForward(name, folds, selections,
    run)`: one continuous portfolio from the first trade session to the data end.
  - `diagnostics(run) -> Diagnostics`: P/L by exit reason and by exit year, trades with < 3 shares,
    gross P/L, costs, and cost drag = costs ÷ gross ("—" when gross ≤ 0). Diagnostics **explain**
    the result and never reach `select`.
  - `window_metrics(run, start)` and `curve_window_metrics(curve, start)`: the "seen before" slice
    of the continuous curves.
  - `gate_p3b(wf, spy_tr, start, end) -> Verdict`.
- **`backtest.wf_report`**:
  - `WalkForwardReport`, `report_stem(data_end)` (`<data end>-strategy-a2-walkforward`),
    `render_markdown`, `equity_csv`, `grid_csv`, `equity_svg`, `variants_svg`. Deterministic: two
    renders are byte-equal.
  - Machine lines `p3b-gate:` (`GATE_KEY`), `last-fold-params:` (`LAST_FOLD_KEY`) and
    `frozen-params:` (`FROZEN_KEY`, `null` when nothing is frozen), read with
    `parse_machine_line(markdown, key) -> str`.
- **`backtest.io.write_wf_report(out_dir, report) -> list[Path]`**: the five files, all rendered
  before any is written.

**Folds** (anchored, yearly). For each trade year Y from 2018 to the data end's year:

- **Tune** on 2015-10-19 → the last session of Y−1.
- **Trade** the first session of Y → the last session of Y, or the data end.

The traded segments form **one** portfolio: 20,000,000 IDR at `prev_session(2018-01-02)`'s FX, with
params switching at each year's first session. Picks for that session use `data_date` = the last
session of Y−1 = `tune_end(Y)`. Each fold selects among all 324 (variant × grid) combinations with
P3's rule (highest tuning-window total return among max DD ≤ 20% and PF ≥ 1.3; ties → lower DD →
combination order), else V0 with the design values. Each variant also gets its own walk-forward,
with the variant fixed and the grid tuned per fold.

**Gate (P3b).** A2 passes only if the combined walk-forward curve (2018-01-02 → data end) beats
total-return SPY over the same span with PF ≥ 1.3 and max DD ≤ 20%, measured with P3's `metrics`
(web parity). The 2022-01-03 → data end window has been seen before. The report shows it only as a
labelled slice of the continuous curves, and it never feeds the gate.

**The report** (`docs/backtests/<data end>-strategy-a2-walkforward.md`) contains, in order:

1. the verdict;
2. data;
3. method, which lists everything tried;
4. every fold's windows, selection, reason and top-10 tuning rows (all 324 per fold are in
   `-grid.csv`);
5. the walk-forward vs both SPY curves;
6. the per-variant curves and selections;
7. the diagnostics;
8. "seen before";
9. the go-live checklist;
10. survivorship;
11. positions open at the end;
12. both charts and links to both CSVs (`-equity.svg`: walk-forward vs SPY; `-variants.svg`: the
    four variants + total-return SPY);
13. the gate verdict;
14. on a fail, the owner's options (handover §8);
15. the machine lines.

**Committed result** (2026-10-02 data, walk-forward 2018-01-02 → 2026-10-02): gate **FAILED**. Strategy A2 fails the P3b gate: walk-forward from 2018-01-02 to 2026-10-02 it returned +9.1% against +187.6% for total-return SPY, with profit factor 1.02 and max drawdown 29.1%, so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; Strategy A's one rework has failed, and P4 stays blocked.
See `docs/backtests/2026-10-02-strategy-a2-walkforward.md`.
Strategy A's one rework has failed. Strategy A is not reworked again on this data, and P4 stays blocked until the owner chooses among the report's options.

**Survivorship.** This is the same gap as P3: 115 index members in the window from
2015-10-19 have no bars at all. It biases every variant in its favour, and the report counts the gap
per year.

**Design §14 does not cover this.** The delisting stress test (delisting-stress-roster-rules) found no break-even for the four quant roster entries even at a total wipeout — but it ran on the **dev window (1996-01-02 → 2015-10-16)**, against the research store's own membership, on the F-family book strategies. This gate is Strategy A2's four variants, on the same post-2015 Neon bars. A walk-forward that reselects on each fold can lean on the survivors harder than one fixed rule, so the bias here is if anything less bounded than P3's. The harness could be pointed at this window, and has not been. Until it is, this gap stays **unquantified** — §14's number must not be read across.

### backtest Strategy B walk-forward (P6a)

This adds to P3 and P3b without changing them. `walkforward.py`, `wf_report.py` and `backtest_wf.py`
are not edited, so A2's P3b report re-renders byte-identically on its own data (checked by
re-running `backtest_wf --end 2026-10-02` on the unchanged Neon data (1,817,429 bar rows): all five files `cmp`-equal). Like the rest of `backtest/`, every module here except `io.py`
is pure, and the purity glob covers it.

- **`backtest.labels`**:
  - `REASONS = ("expire", "tp", "sl", "gap", "time", "forced")`, with `code = index` and -1 for
    unresolved. `COST = 0.001`, which equals `float(sim.COST_RATE)` (tested).
  - `Labels(label, resolved, reason, fill, exit)`: arrays per row.
  - `label_orders(history, symbols, data_dates, limit, tp, sl, end) -> Labels` puts one bracket order
    per row, alone, under design §5 exactly as `sim.step` and the runner apply it, on NYSE sessions,
    reading bars dated ≤ `end` only:
    - The order session is `next_session(data_date)`. With no bar there, or low ≥ limit, the result
      is `expire`, label 0.0.
    - Otherwise it fills at min(open, limit), with no exit check on the fill session.
    - On each later session, in order: the day-5 time stop at the open; a gap through SL or TP at
      the open; SL intraday (first on a both-in-range bar); TP intraday. A session without a bar
      still counts toward the time stop.
    - A symbol whose bars end exits at its last close (`forced`).
    - Anything not resolved by `end` is unresolved (NaN / NaT / -1).
  - `label = exit × (1 − 0.001) ÷ (fill × (1 + 0.001)) − 1`, per share, so it does not depend on
    the share count. `resolved` is the exit session, or the expiry session when unfilled.
  - It is vectorized: session-aligned float matrices, one numpy pass per session offset over the
    still-open rows. A test proves it agrees with a one-order `run_backtest` on a seeded sample:
    the same reason, the same exit date, and the return within 1e-6.
- **`backtest.b_walkforward`**:
  - `B = "B"` and `B_LINEAR = "B-linear"` (curve names), `DECILES = 10`, `TOP_FEATURES = 5`.
  - `candidate_table(market, prepared, is_start, end) -> CandidateTable`: every candidate row from
    `prev_session(is_start)` through `prev_session(end)`, ordered by `(data_date, symbol)`. Its `X`
    equals that date's `Design` rows bit for bit. It carries the `b.bracket` prices (NaN when
    invalid) and `labels` from `label_orders(..., end=end)`.
  - `training_mask(table, fold)` is **the purge**. It keeps rows with a valid bracket whose label
    resolved on or before `fold.tune_end`, with `data_date ≥ prev_session(fold.tune_start)`. A trade
    still open at `tune_end` is excluded.
  - `train_folds(table, folds, kind) -> tuple[FoldModel, ...]`, sequential and in fold order.
    `FoldModel(fold, model, rows, label_mean, label_sum, pred_mean, r2, positive_share, importance)`:
    the in-fold values are information only.
  - `probe_determinism(table, fold) -> bool`: the fold's tree fit at 1 thread and at the default
    give equal digests.
  - `model_schedule(folds, fold_models)` gives a `ParamsSchedule` of `BParams` that switches at each
    year's first session. `walk_forward_b(market, prepared, folds, fold_models, name) -> BWalkForward`
    is one continuous portfolio from the first trade session to the data end.
  - `oos_predictions`, `calibration(pred, label) -> tuple[CalibrationRow, ...]` (10 deciles of the
    out-of-fold prediction, with mean predicted vs realized label) and
    `passed_nights(table, folds, fold_models) -> (passed, traded)`. These **explain** the result and
    never select anything.
  - `gate_p6a(wf, spy_tr, start, end, gated) -> Verdict`.
- **`backtest.b_report`**:
  - `BReport`, `report_stem(data_end)` (`<data end>-strategy-b-walkforward`), `render_markdown`,
    `equity_csv` (`date,b,b_linear,a2,spy_price,spy_tr`) and `equity_svg` (B, B-linear, A2 and both
    SPY curves). It is deterministic: two renders are byte-equal.
  - The machine lines are `p6a-gate:` (`GATE_KEY`), `gated-model:` (`GATED_KEY`),
    `last-fold-model:` (`LAST_FOLD_KEY`: kind, digest, `train_end`, rows and `label_sum` as a JSON
    string holding `repr(float)`, the retrain recipe) and `frozen-model:` (`FROZEN_KEY`, `null` when
    nothing is frozen). Read them with `parse_machine_line(markdown, key) -> str`.
- **`backtest.io`**:
  - `write_b_report(out_dir, report) -> list[Path]` renders the three files before writing any.
  - `MODELS_DIR` (`engine/data/models`).
  - `write_model_artifact(model_dir, data_end, model) -> (path, sha256)` writes
    `b_model.dumps(model)` to `<data end>-strategy-b.pkl`.

**Folds, training and trading.**
- The folds are exactly P3b's (`walkforward.folds`): fold Y trains on 2015-10-19 → the last session
  of Y−1 and trades Y, for 2018 → the data end. No fold selects anything: each one just fits B and
  B-linear on its purged rows.
- The traded segments form **one** portfolio: 20,000,000 IDR at `prev_session(2018-01-02)`'s FX,
  with the model switching at each year's first session. Orders keep the bracket they were placed
  with across a switch.
- Each night's picks are the candidates with a predicted net return > 0.0, ranked descending, ties
  broken by symbol, each with A's design bracket. The simulator fills the free slots in order, and
  a night with no positive prediction trades nothing.

**Gate (P6a).** The gated curve passes only if its walk-forward (2018-01-02 → data end) beats
total-return SPY over the same span with PF ≥ 1.3 and max DD ≤ 20%, measured with P3's `metrics`
(web parity). The gated curve is B, unless the last fold's determinism probe fails. Then the
pre-registered switch gates B-linear, and the verdict sentence says so. B-linear is otherwise
information only and never promotable on this data. A2's walk-forward is on the chart and in the
tables as information.

**The report** (`docs/backtests/<data end>-strategy-b-walkforward.md`) contains, in order:

1. the title;
2. data;
3. method, which lists everything that was fixed in advance;
4. every fold's training summary for B and B-linear (rows, label mean, in-fold R², pred mean,
   positive share, top 5 features by split gain, or by |coef| × std for B-linear);
5. B, B-linear and A2 vs both SPY curves;
6. year by year;
7. the diagnostics: P/L by exit reason and by year, < 3 shares, cost drag, passed nights and the
   calibration table;
8. "seen before" (2022-01-03 →);
9. the go-live checklist;
10. survivorship, with the learned-model caveat;
11. positions open at the end;
12. the chart;
13. the gate verdict;
14. on a fail, the owner's options (b), (c) and (d) (handover §8);
15. the machine lines.

**Committed result** (2026-10-02 data, walk-forward 2018-01-02 → 2026-10-02): gate **FAILED**. Determinism probe: bit-identical at 1 thread and at the default, so B is gated. Strategy B fails the P6a gate: walk-forward from 2018-01-02 to 2026-10-02 it returned +13.3% against +187.6% for total-return SPY, with profit factor 1.03 and max drawdown 57.6%, so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; Strategy B's one round has failed on this data, and P4 stays blocked.
See `docs/backtests/2026-10-02-strategy-b-walkforward.md`. B made +13.3% (PF 1.03, max DD 57.6%)
and B-linear +20.6% (PF 1.05, max DD 32.4%), against +187.6% for total-return SPY; A2's
walk-forward on the same chart made +9.1%.
B's one round has failed on this data. B is not reworked on it, no model is frozen, and P4 stays blocked until the owner chooses among the report's options.

**Survivorship.** The gap is the same as P3's: 115 index members in the window from
2015-10-19 have no bars at all. A learned model can absorb that bias more than a rule can, because
the losers it never saw are exactly the ones it would have needed to learn to avoid. The report says
so.

**Design §14 does not cover this.** The delisting stress test (delisting-stress-roster-rules) found no break-even for the four quant roster entries even at a total wipeout — but it ran on the **dev window (1996-01-02 → 2015-10-16)**, against the research store's own membership, on the F-family book strategies. This gate is Strategy B, a learned model, on the same post-2015 Neon bars. §14 perturbs a market a fixed rule trades; it cannot speak to what a model would have learned from losers absent from its training data, which is the sharper worry here. The harness could be pointed at this window, and has not been. Until it is, this gap stays **unquantified** — §14's number must not be read across.

### sim: trade rules and the book engine (P7a)

Design §5 is now a value. `sim.model`, `sim.lifecycle`, `sim.sizing` and `sim.split_adjust` are not
edited. `DESIGN_V0` runs go through the unchanged `size_picks` + `step` path, through
`backtest.book_runner.run_rules` → `runner.run_backtest`. So the A, A2 and B reports re-render
byte-identically: re-running `backtest`, `backtest_wf` and `backtest_b` on the unchanged Neon data (1,817,429 bar rows through 2026-10-02): all 11 `docs/backtests/2026-10-02-*` files `cmp`-equal (phase 13, 2026-10-04). Every other rule set runs on a second pure engine, `sim.book`.
Both new modules are pure and `Decimal`-only, and `test_sim_purity.py` covers them. Import everything
from `seer_engine.sim`.

**`sim.rules`:**
- Constants:
  - `OPEN_LIMIT_BAND = Decimal("0.02")`;
  - `RESIZE_BAND = Decimal("0.01")`;
  - `SHARE_QUANTUM = Decimal("0.0001")`;
  - `DEFAULT_ETFS = {"SPY", "QQQ"}`, the owner-input default;
  - `LEVERAGED_ETFS = {"SSO", "QLD", "UPRO", "TQQQ"}`.
- `TradeRules` is a frozen value. `__post_init__` validates types (`TypeError`), ints ≥ 1,
  `cost_rate` in [0, 0.05) and a kebab-case `id` (`ValueError`). `cost_model` must be a `str`
  (`TypeError`) in `sim.costs.COST_MODELS`, and `"gotrade"` requires the default `cost_rate`
  (`ValueError`). `DESIGN_V0`'s lever tuple pins `"flat"`, so the bracket engine never uses Gotrade fees.

| Field | Default | Meaning |
|---|---|---|
| `id` | — | kebab-case, unique per preset |
| `engine` | — | `"bracket_v0"` only for `DESIGN_V0` (`ValueError` otherwise, both ways); `"book"` for everything else |
| `cadence` | `"daily"` | the RANK cadence — sessions on which the allocator may choose a new basket: every session (`daily`); the first NYSE session of each ISO week (`weekly`); or the first of each calendar month (`monthly`) |
| `resize_cadence` | `None` | a faster RESIZE cadence split off `cadence` (`None` = one cadence, every rule set before the split). Must be strictly faster than `cadence` and needs `resize=True`, else `ValueError`. On a resize-only session the last rank's basket is kept and rescaled to today's exposure; nothing is ranked, entered or signal-exited |
| `entry` | `"limit"` | `limit`: the target's limit price (a new target with no limit price is bought like `open_limit`); `open_limit`: a buy limit at last close × 1.02 (a limit order, so executable by default); `open`: market-on-open (owner input) |
| `max_positions` | `None` | a cap on non-idle positions (4 only for §5 parity) |
| `time_stop` | `None` | sell at the next open once `days_held >= time_stop` |
| `resize` | `False` | on decision sessions, trade held targets back to weight when the change is ≥ `RESIZE_BAND` × equity |
| `fractional` | `False` | shares quantized down to `SHARE_QUANTUM` (owner input) |
| `dividends` | `True` | credit cash dividends on the ex-date (D11) |
| `idle_symbol` | `None` | the residual weight (1 − Σ targets) held in this instrument on decision sessions; 0% while it has no bar (BIL before 2007) |
| `cost_rate` | `0.001` | per side; any other value is an owner input |
| `cost_model` | `"flat"` | `"flat"`: `cost_rate` per side. `"gotrade"`: every fill pays Gotrade's current measured schedule (`sim.costs`, Sean phase 6); not an owner input. Set by the two `*_GOTRADE` presets (Sean phase 7) |

- Presets (`PRESETS` holds every row below except `V0_BOOK`; ids are unique):

| Preset | id | Engine | Cadence | Entry | Other |
|---|---|---|---|---|---|
| `DESIGN_V0` | `design-v0` | bracket_v0 | daily | limit | 4 positions, time stop 5, whole shares, no dividends: design §5 exactly (= `SLOTS`, `TIME_STOP_DAYS`, `COST_RATE`, tested) |
| `V0_BOOK` | `v0-book` | book | daily | limit | `DESIGN_V0` replayed by the book engine; parity tests only, never in the registry |
| `MONTHLY_HOLD` | `monthly-hold` | book | monthly | open_limit | resize |
| `MONTHLY_HOLD_TBILL` | `monthly-hold-tbill` | book | monthly | open_limit | resize, idle in BIL |
| `WEEKLY_HOLD` | `weekly-hold` | book | weekly | open_limit | resize |
| `DAILY_SWITCH` | `daily-switch` | book | daily | open_limit | no resize |
| `DAILY_SWITCH_TBILL` | `daily-switch-tbill` | book | daily | open_limit | idle in BIL |
| `SWING_T10` | `swing-t10` | book | daily | limit | time stop 10 |
| `SWING_T20` | `swing-t20` | book | daily | limit | time stop 20 |
| `SWING_T20_OPEN` | `swing-t20-open` | book | daily | open_limit | time stop 20 |
| `MONTHLY_RANK_WEEKLY_RESIZE` | `monthly-rank-weekly-resize` | book | monthly rank, weekly resize | open_limit | resize |
| `MONTHLY_RANK_WEEKLY_RESIZE_TBILL` | `monthly-rank-weekly-resize-tbill` | book | monthly rank, weekly resize | open_limit | resize, idle in BIL |
| `MONTHLY_HOLD_FRAC` | `monthly-hold-frac` | book | monthly | open_limit | resize, fractional shares |
| `MONTHLY_RANK_WEEKLY_RESIZE_FRAC` | `monthly-rank-weekly-resize-frac` | book | monthly rank, weekly resize | open_limit | resize, fractional shares; appended to `PRESETS` (now at index 12), so `promote --fractional` maps a `monthly-rank-weekly-resize` winner to it (as `monthly-hold` maps to `monthly-hold-frac`) |
| `MONTHLY_HOLD_FRAC_GOTRADE` | `monthly-hold-frac-gotrade` | book | monthly | open_limit | `MONTHLY_HOLD_FRAC` at `cost_model="gotrade"` (Sean phase 7) |
| `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` | `monthly-rank-weekly-resize-frac-gotrade` | book | monthly rank, weekly resize | open_limit | `MONTHLY_RANK_WEEKLY_RESIZE_FRAC` at `cost_model="gotrade"` (Sean phase 7). These two close `PRESETS`. They are the bases lab methods from M0031 on build on, and `promote` needs a preset of the variant's own id. Their canonical form names `cost_model`, so they digest apart. `tests/test_cost_model_pins.py` pins that every flat preset still omits it |

- `is_rank_session(rules, session) -> bool`, `is_resize_session(rules, session) -> bool` (a resize-ONLY
  session: False without a `resize_cadence`, and False when the session also ranks — ranking supersedes),
  and `is_decision_session(rules, session) -> bool` (either). Without a `resize_cadence`,
  `is_decision_session` is exactly `is_rank_session`, so every call site that predates the split stays
  correct. All three raise `ValueError` for a non-session.
- `LEVERS_SINCE_PINS` / `is_pinned_default(name, value)`: a lever added AFTER the P7a registry, the lab
  trials and the paper roster were pinned, mapped to the value meaning "as before this lever existed"
  (`{"resize_cadence": None, "cost_model": "flat"}`). Every canonical form pinned before the lever leaves such a field out
  while it holds that value — `backtest.registry._canon` (so no pinned candidate digest moves and no
  closed lab trial re-digests through `lab.method.config_digest`) and `paper.roster.rules_dict` (so no
  live paper spec digest moves). A rule set that uses the lever canonicalizes differently.
- `rule_owner_inputs(rules) -> tuple[str, ...]`. The result is sorted and drawn from
  `market-on-open`, `fractional`, `etf:<idle symbol>` (outside `DEFAULT_ETFS`) and `fee`. `fee`
  means a flat `cost_rate` other than 0.1%; `cost_model="gotrade"` never adds it, because the
  schedule is fitted to the owner's own receipts.
- `describe_rules(rules) -> tuple[str, ...]`: one fixed plain-English line per lever. The reports
  and the pre-registration's §5 text use it. Under `cost_model="gotrade"` the costs line is
  read off `GOTRADE.current` (rates, minimum, cap, sell extra, PPN and the regime's start date),
  so it cannot drift from what the simulator charges.

**`sim.book`** (`WEIGHT_QUANTUM = Decimal("0.000001")`):
- `Target(symbol, weight, last, limit=None, stop=None, take=None)`: one instrument wanted after the
  next open, in rank order.
  - `0 < weight ≤ 1`, a multiple of `WEIGHT_QUANTUM`.
  - The prices are 4 dp, with `stop < limit (or last) < take`.
  - A float anywhere is a `TypeError`.
- `to_weight(x)` quantizes down to `WEIGHT_QUANTUM`. `equal_weight(n)`.
- `Position(symbol, shares, mark, entry_date, entry_price, days_held, cost_usd, income_usd, stop, take, exit_pending=False)`:
  one holding episode. `exit_pending` marks a signal exit decided while the symbol had no bar.
- `Book(cash, equity, positions=(), last_session=None)`, with `held()` and `position(symbol)`.
  `new_book(cash_usd)`.
- `Fill(session_date, symbol, side, shares, price, cash_usd, cost_usd, reason)`. The reason is one
  of `entry`, `add`, `trim`, `signal`, `time`, `gap`, `tp`, `sl` or `forced`.
- `Trade(symbol, entry_date, exit_date, entry_price, exit_price, days_held, cost_usd, income_usd, pnl_usd, exit_reason, idle)`:
  one closed episode (shares 0 → > 0 → 0).
  - Dividends are inside `income_usd`.
  - `pnl_usd = income_usd − cost_usd` reconciles with cash exactly.
  - Trims and adds do not create trades.
  - Idle-instrument episodes (`idle=True`) are excluded from trade statistics.
- `BookSnapshot(date, cash_usd, equity_usd, invested_usd)`: `invested_usd` counts non-idle
  positions only, so exposure = invested ÷ equity.
- `step_book(book, session, bars, targets, rules, dividends={}, idle_symbol_ok=False) -> BookStep(book, fills, trades, dividends, rejected, snapshot)`:
  - `targets=None`: not a decision session.
  - `targets=()`: a decision session wanting nothing, so every non-idle position is signal-exited.
  - Σ weight ≤ 1 is checked only when `rules.max_positions is None` (D-A).
  - Order:
    1. Dividends on the ex-date for positions held before S.
    2. Open exits, in symbol order: time stop, then a gap through the stop or the take, then a
       signal exit (a dropped target or `exit_pending`). A position sold this way does not re-enter
       on S.
    3. Trims (`resize`, or the idle symbol) beyond `RESIZE_BAND`.
    4. Buys in rank order, idle last.
       - `max_positions` → `no_slot`.
       - Sizing price: the target's limit, or last × 1.02 (`open_limit`, `open`, and a
         limit-less new target under `limit`). A held target without a limit is never added to.
       - Budget: `min(equity × weight, cash + planned night sells − committed)`.
       - Whole or fractional shares → `too_small`.
       - Fill: strict `low < limit` at `min(open, limit)`, or at the open for `open`. Otherwise
         `unfilled` or `no_bar`.
       - A fill-time cash guard → `cash`.
    5. Intraday stop then take, for positions held before S.
    6. `days_held + 1` and marks.
    7. The snapshot.
  - Buy cash is `q(p × n × (1 + c))`. Sell proceeds are `q(p × n × (1 − c))`.
  - Under `rules.cost_model == "gotrade"`, `_buy_cash`, `_sell_cash` and `_fee` instead use
    `sim.costs.gotrade_cash` (buy `q(p × n) + fee`, sell `q(p × n) − fee`). `Fill.cost_usd` is the
    side-specific fee, and `_shares_for` solves the count exactly with `gotrade_shares_for` (whole
    shares or `SHARE_QUANTUM`), so a buy never overspends despite the $0.10 minimum.
- `close_book_unpriced(book, symbols, rules) -> (book, fills, trades)` sells at the mark with reason
  `forced`, mirroring `sim.close_unpriced`.
- **Parity:** `run_book(PICKS(A), V0_BOOK)` reproduces `run_backtest(STRATEGY_A)` exactly: equal
  snapshots and equal closed trades on seeded synthetic markets (`tests/test_book_runner.py`).

### sim: Gotrade's fee schedule (Sean phase 6)

`sim/costs.py` is pure: no clock, no I/O and no floats. `tests/test_sim_costs.py` reproduces every
receipt in `tests/fixtures/gotrade_fees.json`.

- `CostModel = Literal["flat", "gotrade"]`, `COST_MODELS`, `Side`, `SIDES`, `CENT`.
- `FeeParts(trading, regulatory, ppn, total)`: one order's printed fees to the cent, with
  `total == trading + regulatory + ppn` enforced.
- `FeeRegime(since, trading_rate, trading_min, regulatory_rate, regulatory_cap, sell_extra_rate, ppn_rate)`
  and its `.fees(side, amount)`. The amount is rounded half-up to the cent (at least $0.01; exactly 0
  pays nothing). Then:
  - **trading** is the rate rounded half-up, raised to `trading_min`;
  - **regulatory** is the rate rounded UP and capped, and a sell adds `sell_extra_rate` rounded up
    and uncapped;
  - **PPN** is `ppn_rate × (trading + regulatory)` rounded HALF-DOWN. Only half-down fits all 30 receipts.
- `GotradeSchedule(regimes)`: strictly ascending by `since`. `.current` is the last regime.
  `.regime_on(on)` returns the regime in force on a date (`None` → current; before the first one
  → `ValueError`). `.fee_parts(side, amount, on=None)` delegates to it.
- `GOTRADE`, four regimes. Each `since` is the date of the first receipt seen under that regime:

| since | trading | regulatory | sell extra | PPN |
|---|---|---|---|---|
| 2025-06-10 | none | 0.3% up, no cap | — | none |
| 2025-06-26 | 0.3% half-up, min $0.10 | 0.054% up, cap $0.10 | 0.04% | 11% |
| 2026-03-25 | 0.3% half-up, min $0.10 | 0.054% up, cap $0.11 | 0.04% | 11% |
| 2026-06-16 (current) | 0.2% half-up, min $0.10 | 0.054% up, cap $0.11 | 0.04% | 11% |

  The sell extra rests on one sell receipt (PLTR 2026-10-07). It is deliberately conservative
  until more sells arrive.
- `fee_parts(side, amount, on=None) -> FeeParts`: the module-level shortcut to `GOTRADE`.
- `gotrade_cash(side, price, shares) -> (cash, fee)` is priced at the CURRENT regime. The amount is
  `q(price × shares)`. A buy's cash is `amount + fee`. A sell receives `amount − fee`, with the fee
  capped at the amount.
- `gotrade_shares_for(budget, price, quantum) -> Decimal`: the most shares, as a multiple of
  `quantum`, whose rounded buy cash fits `budget`. It is found by exact bisection, because the
  minimum fee makes cost non-linear in shares.
- Every backtest prices every simulated date at the current regime (`on=None`). The lab asks what a
  method would cost the owner now, not what it would have cost in 2012.

### sim: the owner's contribution schedule (plan phase 5)

`sim/contributions.py` is pure in the same sense as `sim/costs.py`: no clock, no I/O, no floats and
no market calendar. Until it existed every simulated book was a lump sum that never grew —
`backtest.runner` converted `INITIAL_IDR` once and that was all the money there would ever be. The
owner's real plan is 10,000,000 IDR to start and **5,000,000 IDR more on the 25th of every month,
indefinitely** (decided 2026-10-08). This module is that plan as one frozen value; tests in
`tests/test_sim_contributions.py`.

- `ContributionSchedule(amount_idr, day_of_month=25)`: frozen, slotted and hashable. `amount_idr` is
  a finite `Decimal` > 0 and `day_of_month` is 1..`MAX_DAY_OF_MONTH` (28), so a schedule can never
  silently skip February. Anything else is a `TypeError` or a `ValueError`.
- `OWNER_MONTHLY` is the owner's plan as a value: `Decimal("5000000")` on the 25th.
- **The schedule names CALENDAR dates, never sessions.** The 25th is a date on the owner's bank
  statement; whether the NYSE is open that day is the market's business, not the schedule's. A
  runner credits a contribution dated `d` at the OPEN of the first session on or after `d`, which it
  gets by asking `due(previous session, this session)` once per session — so the settlement lag is
  the market calendar's answer rather than a number baked into the schedule.
- `dates_in(first, last)` is every contribution date in the window, both ends inclusive, ascending.
  `due(after, through)` is `dates_in(after + 1 day, through)`: the per-session form, exclusive of
  `after` and inclusive of `through`, so a long gap carries more than one month.
- `usd_at(usd_idr)` converts one deposit, `q(amount_idr / usd_idr)` half-up at `PRICE_QUANTUM` —
  `sim.initial_cash_usd`'s own rounding, so the contributed dollars and the starting dollars are
  measured on one rate and the result is about the strategy rather than about the rupiah.
  `credit_usd(after, through, usd_idr)` is one `usd_at` per due date, each converted and rounded on
  its own, so the book receives the sum of the deposits the owner actually makes and not a rounded
  multiple.
- `Contributions = ContributionSchedule | Sequence[tuple[date, Decimal]]` is what a runner accepts:
  the owner's forward-looking PLAN, or a RECORD of deposits that have already landed and already
  been converted. `credit_for(contributions, after, session, usd_idr)` is where the two become one
  answer to "how many dollars arrive at the open of this session":
  - a **plan** names calendar dates and is priced here at `usd_idr`, this run's single rate — right
    for a backtest, which asks about the strategy and not about the rupiah;
  - a **record** of `(session, usd)` pairs is returned unchanged and `usd_idr` is not consulted at
    all, because each deposit was already converted at the rate of the day it landed. That is right
    for a replay, which must reproduce the dollars a paper night actually wrote; recomputing them at
    one rate would move a stepped book's history the first time the rupiah did. The pairs must be
    strictly ascending dates with `Decimal` amounts > 0, or the record is refused. A record's dates
    are already landing sessions, so the window `after < d ≤ session` selects exactly `d == session`.
- **The lag was measured, not assumed.** Rank sessions are month-start, so a deposit on the 25th
  waits for the next rotation before it can be invested: over the twelve months from 2026-10 the gap
  averages 7.0 calendar days (range 4, February 2027, to 10, December 2026) and 4.2 idle NYSE
  sessions (range 2 to 5). A schedule that baked in a fixed seven-day lag would be wrong in ten
  months of twelve, and one that deposited at the rotation instead would hold a week less idle cash
  every month and so quietly OVERSTATE returns. Reproducing the idle cash is the point.
- **Both runners honour a schedule the same way.** `run_backtest` and `run_book` take
  `contributions=None` by default, so every closed record is a lump sum and unchanged. When one is
  given, each session first asks `credit_for(contributions, data_date, session, usd_idr)`; a
  positive credit raises cash **and** equity before the session sizes anything, and
  `(session, usd)` is appended to `cashflows`. `RunResult` and `BookResult` each gained exactly two fields for this —
  `contributions` (what the run was funded with) and `cashflows` (the dated series a money-weighted
  return is computed from). A deposit is money arriving, never a return.
- **The lab is a caller since lab-realistic-gate R2.** `lab run` and `lab test` pass `OWNER_MONTHLY`
  through `dev.run_registry`, so every newly recorded trial is a funded run; `lab remeasure` and
  `lab costs` pass whatever the trial they are reproducing was recorded on
  (`lab.runner.recorded_contributions`). `backtest_dev` and `lab names --lump` still pass None.

### strategies: allocators and the P7a families

The new modules are pure and flat in `strategies/`, so the purity glob covers them.
`strategies/__init__.py` is unchanged: import from the modules.

- **`strategies.allocator`**:
  - The `Allocator` protocol: `id`, `lookback(params)`, `symbols(params)` (fixed symbols it reads),
    `holds(params)` (fixed symbols it may hold), `uses_members(params)`,
    `targets(history, members, data_date, held, params)`, `prepare(history)` and
    `targets_prepared(prepared, members, data_date, held, params)`.
  - **Contract (P4 identity):**
    - `targets_prepared(prepare(H), …) == targets({s: h.upto(d)}, …)` for every date, holding and
      params;
    - it reads only bars dated ≤ `data_date`;
    - targets are in rank order, with unique symbols and Σ weight ≤ 1 (except `PICKS`, whose §5
      picks may weigh more: the engine's `max_positions` cap picks the entrants, and `step_book`
      checks Σ ≤ 1 only when there is no cap);
    - a symbol with no bar on `data_date` is never a new target;
    - `held` lets a family keep a position, and the engine signal-exits any held symbol the family
      drops. The book runner passes `held` without the idle symbol (D-J).

    `tests/allocatorkit.py` checks this contract for every family.
  - `target_from_close(symbol, close, weight, *, limit=None, stop=None, take=None)` and
    `month_end_closes(h, data_date)`.
  - Adapters and overlays:
    - `PICKS` (`PicksParams(strategy, params, slots=4)`): any bracket `Strategy` as an allocator;
      used for the V0 parity.
    - `BLEND` (`BlendParams(parts)`, each `BlendPart(allocator, params, share)`): F9, core plus
      satellite.
    - `VOLTARGET` (`VolTargetParams(inner, inner_params, signal="SPY", target_vol=0.12, n=20)`):
      L11, which scales the inner weights by `min(1, target ÷ realized vol)`.
  - `prepare(history)` takes no params, so one prepared value per allocator id serves every
    candidate (`LazyPrepared` for `PICKS`, `BLEND` and `VOLTARGET`; D-D).
  - **`MarketAware` and `prepare_for`** (edgar-fundamentals): an allocator that needs more than
    bars — the SEC fact panel, FX, membership — implements `prepare_market(market) -> Any` and so
    satisfies the second `runtime_checkable` protocol `MarketAware`, *in addition to* `Allocator`.
    `prepare_for(obj, market)` is the dispatch: `obj.prepare_market(market)` when the attribute is
    present, else `obj.prepare(market.history)` — exactly what every call site did before — so an
    allocator that does not define it sees no change at all. `obj` may be an `Allocator` or a
    bracket `Strategy`; both have `prepare`. A present-but-not-callable `prepare_market` is a
    `TypeError`, because `runtime_checkable` cannot tell a method from a data attribute and a
    silent fallback would hide a typo as a quietly bar-only allocator.
    - **`prepare_market` is deliberately NOT a member of `Allocator`.** `Allocator` is
      `runtime_checkable` and production sites test `isinstance(x, Allocator)`; adding a member —
      even one with a default body — would make every existing structural implementer fail the
      check. `Allocator`'s member set is therefore unchanged by this phase.
    - An implementer still needs `prepare`: it is an `Allocator` member, and `allocatorkit`'s P4
      identity check drives the plain path.
    - The single real dispatch site is `backtest.dev`'s per-allocator-id prepared cache; nothing in
      the first registry implements `MarketAware` yet.
  - `strategies/__init__.py` is still unchanged: import `MarketAware` and `prepare_for` from
    `strategies.allocator`.
- **`strategies.indicators.return_window(close, n, skip=0)`** (additive):
  `c[:, -1-skip] / c[:, -1-n] − 1`. It follows the same bit-identity rule as the existing windows.
- **Families.** Each family is one singleton plus a frozen params dataclass with
  `as_dict() -> dict[str, str]` in a fixed key order. `Candidate.family` carries the catalogue
  label.

| Module | Singleton (allocator id) | Params | Catalogue | Idea |
|---|---|---|---|---|
| `f_index` | `TIMING` (`F1`) | `TimingParams(hold, signal, rule, n=200)`; rule `sma` / `month_sma` / `abs_mom` / `always` | F1, F10 | hold an index ETF (or a 2× ETF, owner input) only while its signal is above trend |
| `f_index` | `CALENDAR` (`F11`) | `CalendarParams(hold, days_before=1, days_after=3, trend=None)` | F11 | turn of the month, optionally only above trend |
| `f_rotation` | `ROTATION` (`ROT`) | `RotationParams(universe, lookback, top, absolute=True, fallback=None, trend=None)` | F2, F3 | dual momentum and sector rotation, with an absolute filter and an optional bond fallback |
| `f_factor` | `FACTOR` (`FAC`) | `FactorParams(rank, top=10, mom_n=252, mom_skip=21, vol_n=60, pool=50, sizing="equal", min_dollar_volume=2e7, min_price=5, trend=("SPY", 200))` | F4, F5, F6 | 12-1 momentum, low volatility, or momentum among calmer names, on point-in-time index members (SPY excluded) |
| `f_swing` | `SWING` (`F7`) | `SwingParams(slots=4, rsi_n=2, rsi_max=10, sma_n=200, entry="dip", limit_atr=0.5, stop_atr=2.5, take_atr=None, exit_sma=5, exit_rsi=None, min_dollar_volume=2e7, market_trend=None)` | F7 | A's oversold-in-an-uptrend idea with a longer horizon, signal exits and no TP (D12: a new candidate, never A re-run) |
| `allocator` | `BLEND` | `BlendParams` | F9 | a timed SPY core plus a momentum or swing satellite |

F8 (a learned ranker at a longer horizon) and F12 (earnings drift) are not in the first registry
(index Decisions). Either may be appended under D6.

### research store (P7a)

`seer_engine.research` is an **impure** edge: yfinance, Frankfurter and files. It is never Neon (D5).
The store is local and gitignored: `engine/.research/` for the dev window, and since
build-promotion-path phase 2 `engine/.research-test/` for the P7b test window. Every public entry
point takes a keyword `window=` that defaults to `DEV_WINDOW`, so every caller that predates the
parameter builds, loads and refreshes exactly what it did before.

- Constants:
  - `DEV_END = date(2015, 10, 16)`, `DEV_WINDOW`, `MEMBERSHIP_START` and `FX_START`, each equal to
    `backtest.dev`'s (tested);
  - `STORE_START = date(1993, 1, 29)`;
  - `STORE_DIR` (`engine/.research`), and since build-promotion-path phase 2
    `TEST_STORE_DIR` (`engine/.research-test`) and `TEST_WINDOW_START = date(2015, 10, 19)`, the
    first session the test window **trades** — deliberately *not* where the test store's data
    starts, which is `STORE_START` on both windows;
  - `RESEARCH_ETFS`: 21 ETFs (BIL, DIA, EFA, GLD, IEF, IWM, QLD, QQQ, SHY, SPY, SSO, TLT and the 9
    sector SPDRs);
  - `SECTOR_ETFS`, equal to `backtest.registry.SECTOR_ETFS` (tested).
  - `DATA_FILES` (the four required files) and, since edgar-fundamentals,
    `OPTIONAL_DATA_FILES` (now `(FUNDAMENTALS_FILE, ANNOUNCEMENTS_FILE, MARKET_SERIES_FILE)`; the
    third added by eodhd-survivorship-market phase 3, see "Market series" below). `fundamentals.csv` is in the **optional** tuple,
    never a fifth required file: `_read_manifest` requires `DATA_FILES` and *permits* the optional
    ones, and the fingerprint is the sha256 of the sorted `name:sha` lines of the files that were
    actually written. So a store built before this phase keeps loading with a **bit-identical
    fingerprint**, and `--verify` still passes on it.
  - `MANIFEST_KEYS` — still the same **nine** keys — and, since build-promotion-path phase 2,
    `OPTIONAL_MANIFEST_KEYS = {window_name, window_start, window_end}`: the window a non-dev store
    declares, all three or none. They say what the store is **scored** on, never what it holds
    (`store_start` is `1993-01-29` on a test store too), and `dev_end` stays a *code-version pin*
    — the `DEV_END` the building code was compiled against — which a test store carries unchanged.
    **Absent means the dev window.** That is the compatibility hinge, not a convenience:
    `engine/.research` was sealed with exactly `MANIFEST_KEYS`, so a dev build writes none of the
    three and its manifest stays byte-identical. The fingerprint is unaffected either way —
    `fingerprint_of` hashes the `files` map alone — but the manifest's bytes are not, and a shipped
    test reads them. It is the same precedent `OPTIONAL_DATA_FILES` set for a four-file manifest
    from before fundamentals existed.
- The window-bearing helpers — `requested_symbols`, `research_membership`, `unserved_by_year` and
  the private `_overlaps_window` / `_members_start` — each take a keyword `window=` that defaults
  to `DEV_WINDOW`, so every existing caller is unchanged. The membership lower bound stays
  `max(window.start, MEMBERSHIP_START)`: it is a property of the vendored CSVs, not of the window,
  and for the dev window (`start = date.min`) it is `MEMBERSHIP_START` exactly as before.
  `UNSERVED_REASON` is now produced by `unserved_reason(start=STORE_START, end=DEV_END)`; the
  module constant is kept as that function's default call, so `unserved.csv` is byte-identical.
- The window entry points (build-promotion-path phase 2):
  - `test_window(end) -> Window`: `TEST_WINDOW_START` through `end`, equal to
    `DEV_WINDOW.following("test", end)` and asserted equal to it in `tests/test_research_test_store.py`
    so the two spellings cannot drift. `ValueError` when `end` is not after `DEV_END` (that is the
    dev window's territory) or is not an NYSE session. `end` is deliberately **not** a constant: a
    hardcoded end goes stale and would silently change what a recorded test trial meant.
  - `latest_session(now_utc=None) -> date`: an injectable wrapper over
    `dates.last_completed_session` — "data end" at build time, the default end of a
    `--test-window` build.
  - `declared_window(store_dir) -> Window`: what a store says it is for, from its manifest alone.
    It reads no data file and verifies nothing, so a caller can pass the matching `window` to
    `load_store`, which does the verifying. A store with no window keys declares `DEV_WINDOW`. It
    is **not** a way around `load_store`'s refusal — a caller that wants the dev window still
    passes `DEV_WINDOW` and is still refused a test store — and `lab run` and `backtest_dev` never
    call it.
- Files. All are LF text, sorted and deterministic, with prices at 4 dp like `bars`:

| File | Columns | Notes |
|---|---|---|
| `bars.csv` | `symbol,date,open,high,low,close,volume` | split-adjusted, not dividend-adjusted (`auto_adjust=False`), dates ≤ `DEV_END` |
| `dividends.csv` | `symbol,ex_date,amount` | cash dividends from `actions=True`, ≤ 6 dp |
| `fx.csv` | `date,usd_idr` | Frankfurter from 1999-01-04 |
| `unserved.csv` | `symbol,reason` | members overlapping [1996-01-02, `DEV_END`] that yfinance could not serve |
| `fundamentals.csv` | `FACT_COLUMNS`: `symbol,taxonomy,tag,unit,period_start,period_end,val,accn,form,fy,fp,filed` | **optional** (edgar-fundamentals), written only with `--with-fundamentals`; sorted, in `io.FACTS_COPY_SQL`'s encoding |
| `manifest.json` | — | counts, a sha256 per file, and `fingerprint` (the sha256 of the sorted `name:sha` lines); no timestamps |

- `build_store(store_dir, *, downloader=None, fetch_fx=None, sleep=time.sleep, batch_size=40, data_dir=None, facts=None, window=DEV_WINDOW)`:
  - `window` is the window the store is built for and declares. On the default every byte is what
    it was before the parameter existed — same symbols, same range, same `unserved.csv` text, same
    nine manifest keys, same fingerprint. Pass `test_window(latest_session())` for the test store.
  - **the data range follows `window.end` alone**: always `STORE_START..window.end` for bars and
    `FX_START..window.end` for FX, on either window. A test store therefore carries the *same* deep
    history as the dev store plus everything after it.
  - **the universe follows the window at both ends**: `requested_symbols(data_dir, window=window)`
    is every member overlapping `[max(window.start, MEMBERSHIP_START), window.end]` —
    `[1996-01-02, DEV_END]` on the dev window, unchanged. On the test window every post-2015 joiner
    is in and everything that left before 2015-10-19 is out, because no test-window session ever
    ranks, holds or exits one; `members_on(t)` is the same set either way and only the crawl size
    differs. A membership interval closing in 2018 also stays closed instead of reading as open.
  - facts are **not** filtered by `window`: `FundamentalPanel` selects point-in-time on `filed <= t`
    at read time, so a later filing is invisible on an earlier session, and filtering here would
    rewrite `fundamentals.csv` and move the dev store's fingerprint for no gain.
  - `unserved.csv` names the range the **download** covered (`STORE_START..window.end`), which is
    byte-identical to `UNSERVED_REASON` on the dev window;
  - downloads are throttled and batched, with rate-limit backoff like `backfill`;
  - rows after `window.end` are dropped defensively;
  - it writes every file to a temp dir and then renames it, so the build is all-or-nothing
    (`ResearchStoreError` on failure);
  - `facts` (edgar-fundamentals) is the SEC point-in-time panel as a plain sequence of
    `fundamentals.Fact`, rendered by `fundamentals_lines(facts)` into `fundamentals.csv` and added
    to the manifest. `None` — the default, and every caller that predates fundamentals — writes no
    `fundamentals.csv` at all. `research.py` never opens a connection for them: the command passes
    them in (see `--with-fundamentals` below), so the "Never Neon" invariant (D5) is unchanged.
  - it returns the manifest.
- `load_store(store_dir, *, data_dir=None, window=DEV_WINDOW) -> ResearchData(market, dividends, spy_dividends, fingerprint, manifest, unserved, window)`:
  - `window` is the window the **caller** expects, and `ResearchData` now carries the window the
    store declares. The default means every dev path — `lab run`, `backtest_dev`, this module's own
    refresh — gets the dev guarantee without passing anything, and a mis-pointed
    `SEER_RESEARCH_STORE` aimed at the test store fails loudly instead of silently running the dev
    pipeline on test data. A test-window caller must ask for it explicitly, normally by passing
    `declared_window(store_dir)` straight back in.
  - **it refuses a window mismatch before it reads a data file**: a dev store where a test store is
    expected, or the reverse, is a `ValueError` naming both windows. The two are not
    interchangeable — the test store holds the same history *and* every session after `DEV_END`, so
    loading one where the other is expected would run the dev pipeline on unseen data (D9).
  - it verifies every sha256 and rejects any row dated after `window.end` (`ValueError`, also for a
    missing store). That is the data-level guard of D9; on the dev window the refusal message is
    unchanged, word for word.
  - Its `Market` takes membership from `membership.compute_universe()` through
    `io.merge_intervals`, offline. Its `fundamentals` is `_read_fundamentals(fundamentals.csv)`
    when the manifest lists that file and `EMPTY_FUNDAMENTALS` otherwise (edgar-fundamentals), so
    a pre-fundamentals store loads to a market with an empty panel rather than an error.
- `run_checks(data, vendored)`: the three data checks `research_store --verify` prints. Two of
  them now follow `data.window` (build-promotion-path phase 2): `check_spy_sessions` defaults its
  `end` to the store's own window end, and `check_spy_dividends` compares on the overlap
  `[first vendored ex_date, min(window end, last vendored ex_date)]`. The clamp is what stops a
  test store built past the vendored file's last row from reading as a mismatch; on the dev window
  the window end is still the earlier bound, so neither check weakens.
- `refresh_fundamentals(store_dir, facts, *, data_dir=None, window=DEV_WINDOW)`, the
  fundamentals-only refresh (fundamental-panel-coverage): reuses an existing store's four
  required files byte for byte, writes a new `fundamentals.csv`, re-seals and `_swap_in`s. The
  manifest's copied counts (`bar_rows`, `dividend_rows`, `fx_rows`, `symbols_requested`,
  `symbols_served`) are carried over, never re-derived from a download. `window` must be the window
  the store declares (pass `declared_window(store_dir)`); `load_store` refuses a mismatch, so a dev
  refresh can never be aimed at the test store or the reverse, and `_seal` re-declares the same
  window — refreshing a store never changes which window it is for.

**The committed store** (built in phase 4, verified in phase 13): fingerprint `5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a`.
- 2,490,793 bar rows; 539 of 1,061 symbols served, and 522 members unserved. Of those 522, **404
  left the index inside the dev window and 118 were still members on its last day** — a split that
  matters because only the 404 are a death a stress test can inject; what is missing for the other
  118 is twenty years of prices, not an exit, and design §14 names their cost as unmeasured.
- 28,206 dividend rows and 4,300 FX rows.

**The current train/eval store** (fundamental-panel-coverage, 2026-10-05): fingerprint
`399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8`, superseding
`e597367bb6806d7edc2f9af4033b26c366aae92517207b4e71daad96346fcca3`.
Same bars — the refresh copied them byte for byte — with a panel rebuilt from facts filed since
2009-01-01 against the re-vendored `ticker_cik.csv`: 1,213,303 facts over 869 symbols. Dev-window
coverage **0.3151** (`research_store --coverage`, 75 of 238 monthly samples); it was **0.0378**
before. That is better data and not a valid test: the dev window opens in 1996 and XBRL starts
around 2009, so a fundamentals method still cannot reach the lab's `>= 100 trades` gate on it.
The store syncs between machines with `/sync-research-store` (`push`/`pull`, content-addressed on
this fingerprint, Vercel Blob); push it with `--keep 0`, because a plain `push` prunes to the
newest three versions.

**That fingerprint cannot move**, and build-promotion-path phase 2 was built around keeping it so:
it is the identity `/sync-research-store` keys on and the one every recorded lab trial was measured
against. The dev store's manifest therefore still carries exactly nine keys — the window keys are
optional and a dev build writes none of them — and the dev store has **no test-window twin inside
it**: the test window is a separate directory, `engine/.research-test`, with no fingerprint on
record until something is actually promoted.

Both coverage figures above are **upper bounds** — the measure reads no bars, so membership,
`min_price` and `min_dollar_volume` are not applied.

yfinance has no delisted tickers, so the dev window's survivorship gap is far larger than the 115
members since 2015, and single-stock dev results are optimistic (D4). The report counts the gap year
by year (41.4% of member-sessions over 1996–2015 have no bar). ETF-only candidates have no such bias.

**How optimistic, measured** (design §14, delisting-stress-roster-rules phase 2): the gap does not
explain the edge. Injecting deaths into the priced survivors at the store's own measured rate
(4.002%/yr unpriced exits; 5.091%/yr all exits) and re-running 100 seeds per assumed loss, all four
quant roster entries still beat total-return SPY **even when every vanishing company is assumed to
go to zero** — +0.73 (RMW-FR), +3.69 (RAW-FR), +2.30 (MOM-FR) and +0.11 (MVW-FR) points a year at
`r = -100%`. There is no break-even on the grid at the measured rate. Two caveats the number does
not carry: at the pessimistic 5.091%/yr rate MVW-FR's break-even lands on the scale at **-85.8%**
and RMW-FR sits at +0.01 pts/yr, so for those two the conclusion rests on the measured rate; and
the injected death is abrupt, which makes the whole result an **upper bound** on the damage.

**The purpose marker** (eodhd-survivorship-market phase 1). `PURPOSE_KEY = "purpose"`,
`SURVIVORSHIP_PURPOSE = "survivorship-check"` and `PURPOSES` (that one value) name what a store that
is **not** for recording trials is for; `SV_STORE_DIR` is `engine/.research-sv`. The key is optional,
sits outside both `MANIFEST_KEYS` and `OPTIONAL_MANIFEST_KEYS`, and is not hashed, so the dev and
test manifests are unchanged and their fingerprints cannot move. `_seal(..., purpose=)` writes it
only when given (ValueError on an unknown value); `build_store` never passes it. `_read_manifest`
accepts it beside either manifest shape and rejects an unknown value; `_refresh_optional` carries
it, so a refreshed survivorship-check store stays marked. `load_store` surfaces it as
`ResearchData.purpose` (None for an ordinary store), and `declared_purpose(store_dir)` reads it from
the manifest alone, without a full load. The refusal lives in `lab/runner.py`:
`survivorship_refusal(what, purpose)` builds the one `store.LabError` every trial-writing path gives,
and `refuse_survivorship_store(data, what)` raises it when `data.purpose` is set (via `getattr`, so
a hand-built fixture without the field is an ordinary store). It is the first statement of
`runner.run_method`, `runner.run_test`, `remeasure.measure`, `remeasure.remeasure` and
`remeasure.remeasure_seed`, and `commands/lab.py`'s `_run` asks `declared_purpose` before it even
discovers the method — so a marked store exits 2 with nothing ran and nothing written.

**Market series** (eodhd-survivorship-market phase 3). `MARKET_SERIES_FILE = "market_series.csv"`,
`MARKET_SERIES_HEADER = "series,date,value"`, and `MARKET_SERIES_NAMES` (the ten names, sorted; the
only ones the file may hold). The file is the third `OPTIONAL_DATA_FILES` entry and never in
`DATA_FILES`, so `price_fingerprint_of` (which hashes `DATA_FILES` alone) does not move when a store
gains it, and a store without it loads exactly as before. `market_series_lines(rows, *, end=DEV_END)`
turns `(series, date, Decimal)` rows into deterministic, sorted lines (normalized decimals) and
raises on an unknown series, a date after `end` (D9) or before `STORE_START`, a non-finite value or
a repeated `(series, date)`. `refresh_market_series(store_dir, rows, *, data_dir=None,
window=DEV_WINDOW)` rewrites the file through `_refresh_optional`, the same discipline as
`refresh_announcements`: rows checked first, every other file carried over byte for byte, the
store verified and swapped in whole. The private reader is as strict as the others and also refuses
any CR byte itself (read_text's universal newlines would hide a CRLF from the shared `_data_lines`);
values may be zero or negative, never NaN or infinite. `load_store` builds `Market.series` from it
when the manifest lists it, else `EMPTY_SERIES`. `build_store` never writes it.

### survivorship (eodhd-survivorship-market phase 1)

`seer_engine.survivorship` is pure apart from `read_series(cache, symbol)`, which reads one
symbol's cached EODHD answers and nothing else. `commands/survivorship_store.py` is its impure edge.
It turns raw EODHD history into bars in the dev store's conventions (split-adjusted, not
dividend-adjusted, 4 dp, integer volume).

- **Types:** `RawBar`, `Split`, `RawDividend`, `SourceSeries` (source-agnostic, the seam for a
  second source), `CleanBar`, `Cleaned` (the bars, dividends, `action` and reason), `YearCoverage`.
  Actions: `KEPT`, `REPAIRED`, `TRIMMED`, `DROPPED`.
- **`clean_symbol(series, member_days, sessions)`** runs the rules in order, each a named,
  calibrated constant: drop invalid and zero-volume filler rows; apply a listed split only when the
  raw close actually fell by its ratio (EODHD's "raw" sometimes already carries it); clip to the dev
  window's NYSE sessions; cut the series at holes over `HOLE_SESSIONS` and **trim** segments wholly
  outside the membership span (a reused ticker spliced on, e.g. CTX, BSC), **dropping** a symbol with
  no segment inside it; end `TAIL_GRACE_SESSIONS` after the last member session; split-adjust;
  rescale unlisted scale breaks (open, close and inverse volume all agree); remove short spikes;
  rescale wrong-scale islands; then judge each remaining move beyond `JUMP`. A move with a volume
  surge, or a fall near the end of membership or of the series, is **genuine and kept** (ENRNQ,
  WAMUQ, CVH: removing a collapse would bring the bias back); any other is a vendor error,
  **repaired** by rescaling the rows before it or cut when outside the span. More than
  `ABSURD_MAX_MOVES` suspect or genuine moves inside the span **drops** the symbol. Finally bars the
  loader would refuse are fixed or removed, and dividends (USD, clipped to the kept bars, refused
  above `MAX_DIVIDEND_YIELD`) are attached.
- **`best_of(candidates)`** picks, among several cleaned candidates for one symbol, the one
  covering the most member days. `member_sessions()` and `coverage_by_year()` do the coverage
  arithmetic (member-days served per year, before and after); `bar_line`, `amount_text` and
  `merge_sorted_lines` write the store's lines in the dev store's format.

### survivorship_alias (eodhd-survivorship-market phase 2)

`seer_engine.survivorship_alias` finds the EODHD code an index member with no usable series traded
under. Offline apart from `fetch`, which goes through an injected `eodhd.Client`-like object.

- **Candidates:** `load_listings` / `load_sources(cache_root, data_dir)` read
  `symbols-US-delisted.json` / `symbols-US-live.json` from the cache, `ticker_cik.csv`,
  `ticker_aliases.csv` and `data/eodhd_alias_hints.csv`. `candidates(symbol, sources)` returns up
  to `MAX_CANDIDATES` codes in `MATCH_ORDER` (`hint`, `name`, `alias`, `class`, `bankruptcy`,
  `code-variant`), skipping `SKIP_TYPES` listings and never the store symbol's own code.
- **Acceptance:** `choose` / `resolve(members, sources=, alias_dir=, by_symbol=, clean=)` give one
  `Resolution` (`symbol`, `code`, `name`, `matched_by`, `accepted`, `reason`) per member. A
  candidate fits when its series has at least `MIN_MEMBER_ROWS` rows on the member's index days and
  `phase1_clean` (phase 1's `clean_symbol`) does not drop it. Two fits that are different series
  (`same_series`: closes within `SAME_CLOSE_TOL` on `SAME_SERIES_SHARE` of shared days) are
  "ambiguous" and resolve to none, unless exactly one came by hint or name (`NAMED`).
- **Cache:** `fetch(client, alias_dir, members, ...) -> FetchStats` writes `probe/<CODE>.json` per
  candidate and `<SYM>.json` per accepted member under `<cache>/alias/` (`ALIAS_DIR`, `PROBE_DIR`)
  and nothing else. `targets` lists the members still without a usable series.
- **Into the build:** `alias_sources(alias_dir, resolutions)` turns accepted alias files into
  `survivorship.SourceSeries` with source `ALIAS_SOURCE = "eodhd-alias"`; `report_rows` /
  `report_text` produce `alias_report.csv` (`REPORT_HEADER`).
- **`eodhd` additions:** `exchange_code(code)` (a symbol-list code verbatim plus `.US`, case kept:
  `DELL_old` -> `DELL_old.US`), and `Client.eod`, `Client.splits`, `Client.dividends_by_code`,
  which take such a code and return None on 404.

### backtest book runner (P7a)

`backtest/book_runner.py` is pure (covered by `tests/test_strategy_purity.py`); tests in
`tests/test_book_runner.py`.

- **`run_book(market, allocator, params, rules, start, end, *, prepared=None, dividends=..., initial_idr=INITIAL_IDR, usd_idr=None, kickoff=None, contributions=None) -> BookResult`**:
  drives an `Allocator` under book `TradeRules` (`rules.engine == "book"`) through `sim.book.step_book`
  over every NYSE session in `[start, end]`, in `run_backtest`'s shape. On a rank session
  (`sim.rules.is_rank_session`) the allocator maps history through `data_date = prev_session(S)`
  to target weights (via `targets_prepared` when `prepared` is given, else `targets`); other sessions
  pass `None`. On a resize-only session (`is_resize_session`, only with `rules.resize_cadence`) the
  allocator is called the same way but its answer is used for its TOTAL weight alone: `_rescaled`
  keeps the last rank session's basket, restricted to what is still held, with every weight × `k =
  Σ(fresh) / Σ(last rank)` and `last` refreshed to today's close (falling back to the book's mark),
  dropping `limit`/`stop`/`take`. So Σ matches what the allocator wants today while the names are
  frozen, and the freed weight goes to `idle_symbol` or cash. `k` is exact for an overlay that scales
  a fixed-width basket (vol targeting); for an allocator whose basket WIDTH varies it conflates
  "fewer names" with "less exposure". A resize session before the window's first rank has no basket
  and is not a decision session at all (the allocator is not called). With `rules.idle_symbol` the residual `1 - sum(weights)` goes to that instrument.
  Held-symbol dividends with ex-date S are passed only when `rules.dividends`. Positions with no bar
  on S or later are force-closed (`close_book_unpriced`). `usd_idr` defaults to
  `market.usd_idr_on(start)`. `DESIGN_V0` rules are a ValueError here.
  `BookResult` carries snapshots, fills, trades, `open_at_end`, `dividends_usd`, `costs_usd` and
  `rejections` (by reason).
- **`run_rules(market, strategy_or_allocator, params, rules, start, end, *, prepared=None, dividends=..., usd_idr=None) -> RunResult | BookResult`**:
  the single P7a dispatch. `DESIGN_V0` (`"bracket_v0"`) with a `Strategy` goes to the unchanged
  `run_backtest` (so A, A2 and B stay byte-identical by construction; dividends ignored; `usd_idr`
  must be None or equal `market.usd_idr_on(start)`); book rules with an `Allocator` go to
  `run_book`; any other pairing is a TypeError.
- **`run_stats(RunResult | BookResult) -> RunStats`**: what the dev report needs from either
  result: `metrics` (non-idle trades for a book run, plus `avg_days_held` and `exit_reasons`),
  `exposure`, annualized `turnover`, `costs_usd` (a book run's `Fill.cost_usd`, so Gotrade's fees
  under `cost_model="gotrade"`; always the flat rate for a `DESIGN_V0` RunResult), `gross_pnl_usd`, `cost_drag`, `dividends_usd`,
  `daily_returns`, `sharpe` (population stdev, x sqrt(252)), `year_returns` and `worst_year`.
  Floats exist only here, summed left to right as in `backtest.metrics`.
  For a **funded** run — `cashflows` non-empty, which since lab-realistic-gate R2 is every
  `lab run` and `lab test` — `_daily_returns` and `_year_returns` are cashflow-adjusted:
  a deposit is credited at the OPEN of the session it lands on and earns that session, so it
  belongs in the DENOMINATOR of the return into that session (`cur / (prev + flow_t) - 1`,
  `metrics.flow_map`), and a calendar year's return is chained from those session returns — the
  time-weighted return of the year — instead of taken end-over-end. A deposit is money arriving,
  never a return: uncorrected, the smoke fixture reported a single +50.00% session, an annualized
  Sharpe of 2.6524 for a book whose honest Sharpe is 0.2620, and a "worst year" of +74.3%. The
  Sharpe one is a **gate condition**, not a display number — these returns feed
  `commands.backtest_dev.daily_moments` -> `dev.deflated_sharpe` -> the `trials.dsr` the luck gate
  reads — while `worst_year` is recorded and displayed but is none of `dev.make_row`'s five
  checks, so correcting it moves a published number rather than a verdict. With no cashflows both
  functions take their original expressions verbatim, so every unfunded run, every existing test
  and all 128 recorded trials are byte-identical.

### backtest: dev runner, report and registry (P7a)

These add to P3, P3b and P6a without changing them, on top of the book runner above. Every module
here is pure, and the purity glob covers it; the one writer is `backtest.io.write_dev_report`.

- **`backtest.window`**: one frozen value object and nothing else — `Window(name, start, end)`,
  with `name` in `WINDOW_NAMES = ("dev", "test")`, `covers(d)` and
  `following(name, end)` (the window opening on the session after this one). Pure, and the purity
  glob covers it. It holds no date of its own, so it adds no third copy of `DEV_END`: the dev
  window is a constant in each of the two modules that already own one (`dev.DEV_WINDOW` and
  `research.DEV_WINDOW`, pinned equal by `tests/test_backtest_window.py`, as the two `DEV_END`s
  are). `start = date.min` means *no lower bound* — that is the dev window, whose backtests open
  as early as the data allows (SPY's first session, 1993-01-29).
- **`backtest.dev`**:
  - Constants: `DEV_END = 2015-10-16`, `DEV_WINDOW = Window("dev", date.min, DEV_END)`,
    `MEMBERSHIP_START = 1996-01-02`, `FX_START = 1999-01-04` and `MAX_CANDIDATES = 60`.
  - **The window is a value, not a module constant.** Every entry point below takes a `window=`
    argument that **defaults to `DEV_WINDOW`**, so a caller that passes nothing gets the D9 dev
    behaviour it has always had, byte for byte; `DEV_END` itself is unchanged.
  - `check_dev_session(d, window=DEV_WINDOW)` raises `DevWindowError` (a `ValueError`) after
    `window.end` — `DEV_END` on every path that passes no window. Every public entry point calls
    it before anything else.
  - `Candidate(id, family, rules, allocator, params, rationale, added, owner_inputs)`.
    `candidate_owner_inputs(c)` returns `rule_owner_inputs` plus every held ETF outside
    `DEFAULT_ETFS`, plus `leverage` for a held leveraged ETF. An empty tuple means executable under
    the conservative defaults.
  - `candidate_window(market, c, *, window=DEV_WINDOW) -> (start, window.end)`. The start is the
    first session where every instrument the candidate reads, and SPY, has its lookback. A member
    family also starts no earlier than `MEMBERSHIP_START`, and no candidate opens before
    `window.start` — a floor that can never bind on the dev window, whose start is `date.min`.
  - `run_candidate(market, dividends, spy_dividends, c, *, prepared=None, window=DEV_WINDOW,
    initial_idr=INITIAL_IDR, contributions=None, contribution_fx=None)` and
    `run_registry(market, dividends, spy_dividends, registry, *, on_result=None, window=DEV_WINDOW,
    initial_idr=INITIAL_IDR, contributions=None, contribution_fx=None)`
    run sequentially, in registry order, with one prepared value per allocator id — built by
    `strategies.allocator.prepare_for(allocator, market)` (edgar-fundamentals), so a `MarketAware`
    allocator gets the whole `Market` (fundamentals included) and every other one gets exactly the
    `allocator.prepare(market.history)` it got before. The candidate's market copy carries
    `fundamentals` over with `history` and `membership`, so a long window keeps the panel. Starting capital is
    a run input: `initial_idr` (default `runner.INITIAL_IDR`, 10,000,000 IDR) is forwarded through
    `_run` to `run_rules`, which opens with
    `initial_cash_usd(initial_idr, usd_idr_on(max(start, FX_START)))`; a window starting before
    `FX_START` runs on a market copy whose `fx` is that single rate (D-C). FX before 1999 affects
    only that conversion, never a decision.
  - `DevRow` holds the stats and both SPY curves on the candidate's own window and cash. SPY's
    dividends come from the store. The curves pay the candidate's `rules.cost_model` (`spy_curves(...,
    cost_model=c.rules.cost_model)`), so a `"gotrade"` method and its benchmark pay the same fees. Its trailing `window` field (defaulted to `DEV_WINDOW`) records
    which window produced the row; `make_row(..., window=DEV_WINDOW)` carries it over.
  - `finalists(rows)` is D8:
    - **eligible** means beating SPY TR, max DD ≤ 20%, PF ≥ 1.3, ≥ 100 closed trades, and no owner
      input;
    - the eligible rows are ranked by MAR (CAGR ÷ max DD), ties by id;
    - the top 3 are kept, at most one per family.
  - `deflated_sharpe(sharpe_daily, n_trials, var_trials, t, skew, kurt)` follows Bailey & López de
    Prado (2014).
- **`backtest.dev_report`**:
  - `DevReport` and `report_stem(run_date)` (`<run date>-p7a-dev-exploration`);
  - `preregistration_name(run_date)` (`<run date>-p7b-preregistration.md`);
  - `render_markdown`, `rows_csv`, `curves_csv`, `frontier_svg` and `render_preregistration`.
  - The run date appears in file names only, so a re-run is byte-identical. Two renders are
    byte-equal.
- **`backtest.registry`**:
  - `REGISTRY` holds 54 candidates across 11 families. 11 of them carry owner inputs and cannot be
    finalists until the owner confirms.
  - `candidate_digest(c)`.
  - `tests/test_registry.py` pins every `(id, digest)`, so the tuple only grows (D6).
- **`backtest.io.write_dev_report(out_dir, plans_dir, report) -> list[Path]`** renders all five
  files (`dev_report_files`) before writing any.

**Committed result** (research store `5451195fd552`, dev window ≤ 2015-10-16, registry at
`b2ec090`): 54 candidates tried, 0 eligible under D8.

None eligible: of 54 candidates, 35 beat total-return SPY on their own windows, 0 kept max DD ≤ 15%,
40 reached PF ≥ 1.3, 33 made ≥ 100 closed trades and 43 needed no owner input; none met all five.
The best MAR was `F4-MOM12-N20-TREND` (F4): CAGR +16.2% against +7.9% for total-return SPY, max DD
22.2%, PF 2.27, 1,154 trades, MAR 0.73; it failed on max DD ≤ 15%. See
`docs/backtests/2026-10-04-p7a-dev-exploration.md` and its frontier chart. P7b does not run; the
pre-registration file records "none eligible".

### lab: pre-registration (build-promotion-path phase 3)

`lab/prereg.py` owns the `docs/lab/prereg/MNNNN.md` format — its writer, its parser and the
committed-file gate. Nothing in it loads a research store, runs a backtest or writes a `trials` row.

- **Why a file at all.** The lab gets one look at the test window per configuration, and the database
  already enforces that much: `UNIQUE(config_digest, window)` plus the append-only triggers. What a
  database cannot enforce is *which* configuration the look is spent on, and it cannot stop a
  disappointing answer from retroactively becoming a different question. The committed markdown file
  is that missing half, and the property is a conjunction of three facts: the file's `config_digest`
  is copied out of the recorded dev `trials` row and never recomputed from the live method file; the
  method file still hashes to the `source_sha` frozen when it ran; and the file is in git, unmodified,
  before the look. `docs/lab/prereg/README.md` states the same contract for a human reader.
- `PreregError(store.LabError)`: every refusal in the module. Being a `LabError` means
  `commands/lab.py` already turns it into exit 2 and no caller needs a second `except`.
- `Prereg`: a frozen dataclass of the file's front-matter block — `method`, `candidate`,
  `config_digest`, `rules_id`, `allocator_id`, `dev_trial`, `dev_window`, `test_window`, `gate`,
  `mar`, `dsr`, `n_trials_at_run`, `store_fingerprint`, `git_sha`, `date`, and since
  lab-hard-gate phase 2 `folds` and `family_state`. **Every field is a `str`**: the file is the
  record and this value is a reading of it, not a parallel source of truth, so
  `parse(render(p, name)) == p` exactly with no number formatting in the round trip. `FIELDS` is
  the tuple of names, taken from the dataclass; `REQUIRED` is the fifteen that carry no default,
  derived rather than retyped so a new defaulted field can never tighten the parser.
- `folds` and `family_state` are **the hard gate's record of what this method cleared**, written
  at promotion and never recomputed afterwards. `folds` is the walk-forward record in
  `Record.summary()`'s own words (`"3 of 4 folds"`, or `"2 of 4 folds, pick changed"`), and
  since hardgate D11 `fold_text` also records how many folds the pre-registered variant won alone
  (`"<candidate> alone won W of N"`); `family_state` is the kin's state at that moment, and
  `family_text` names family, ancestry and ingredients (D12). They are the only two fields `parse`
  tolerates as **absent**, filling them with a stated legacy value, because
  `docs/lab/prereg/{M0002,M0021,M0022,M0029}.md` were committed before the gate existed and a
  pre-registration is written once and never rewritten (Decision D5). Every file written from
  here on carries both, so a reader a year from now sees the bar *this* method cleared rather
  than today's bar.
- `render(p, name) -> str` / `parse(text) -> Prereg`: the exact bytes of the file, and the reading of
  them. `parse` is strict on purpose — the block must be the first thing in the file, must be closed
  by its second `---`, must carry every key in `FIELDS` exactly once and must carry nothing else. An
  unknown key is an error rather than a shrug, so a misspelled `config_digest` can never read as "no
  digest given".
- `require_committed(candidate_id, *, directory=None) -> Prereg`: **the gate `lab test` calls before
  it spends the look**, and the only reason the module exists — a test number must not be reachable
  unless the thing being tested was named, in git, first. It refuses when `candidate_id` is not a
  `MNNNN-SUFFIX` candidate id (a bare method id is an ambiguity to refuse, not a thing to guess at),
  when `docs/lab/prereg/<method>.md` does not exist, when git does not track it or it has staged or
  unstaged changes, when it does not parse, and when it pre-registers a different method or a
  different candidate. It deliberately does **not** look at the database: the method's status and the
  one-look rule are the caller's refusals, so a missing file and a wrong status give different
  messages rather than one vague one.
- `check_digest(p, digest, *, directory=None) -> None`: `require_committed` matched the candidate's
  *id*; this matches what the candidate *does*, which is the match that counts — an id can be reused,
  a digest cannot. The caller passes the digest of the thing it is about to run.
- `check_source(method_id, row, trial) -> Path`: two equalities, both `PreregError` when broken — the
  method file's sha256 is the `source_sha` frozen when the method ran, and the candidate the trial
  names still digests to the trial's `config_digest`. The second is checked even though the first
  mostly implies it, because `config_digest` canonicalizes `TradeRules` and allocator params defined
  in *other* files, so the method file's own bytes do not pin it. No git call: `lab run` already
  refused an uncommitted method file before recording those trials.
- `promote_method(conn, method_id, *, git_sha, today=None, directory=None, check_method_file=True) ->
  Promotion`: what `lab promote` runs; the CLI section above has its ordering, idempotence and
  refusals. `Promotion(prereg, path, trial_n, status, wrote_file, moved_status)` is what it did, for
  the caller to print. `check_method_file=False` skips `check_source` and exists for tests, which
  build `trials` rows with no method file behind them; nothing in the CLI passes it.
- `path_for(method_id, directory=None)`, `method_of(candidate_id)`, `repo_path(path)`,
  `committed_problem(path)`, `PREREG_DIR`, `FENCE`, `MARKER`.
- `gate_text(conn=None)` is **built** from `backtest.dev.FAILURE_LABELS`, `store.DSR_MIN` and
  `store.DSR_POLICY` rather than retyped, so a pre-registration cannot claim a condition the code
  stopped applying, a bar the owner has moved, or an N the gate stopped deflating by. What it
  states is the **dev** gate the variant passed to become `dev-eligible`: the five P7a D8
  conditions plus `DSR >= DSR_MIN` (0.90 since 2026-10-07, the owner's risk appetite — design
  §7.1), deflated by the N the policy in `store.DSR_POLICY` resolves to (`methods` = one look per
  distinct method, floored at the measured participation ratio, since 2026-10-08; it was
  `all-trials` = every dev trial in the lab before that). `promote_method` always passes the
  connection, so every committed file carries the threshold, the policy name *and* the count it
  resolved to that day; the `conn=None` form stops short of the count and exists for refusal
  messages and for tests that build a `Prereg` with no database. It is *not* the gate the one
  test-window look is judged by: that is the five D8 conditions alone, because a pre-registered
  look has no selection among results to deflate, so DSR is recorded on the test trial and is not
  a condition. `render` says so in the file's prose, so a reader of the pre-registration cannot
  mistake one for the other.
- `test_window_label()` is `dates.next_session(dev.DEV_END)..data end` — the same start
  `lab.store.snapshot` publishes as `gate.testStart`. The end is deliberately not a date this step
  can know (the test-window store is built on first promotion and reaches the latest session
  available then), so the exact end is pinned afterwards by the `trials` row `lab test` writes.
- `store.best_dev_eligible(conn, method_id) -> sqlite3.Row | None` (a pure addition to `lab/store.py`):
  the method's best eligible dev trial by MAR, ties broken on the trial number, so the answer is
  exactly one row and the same row every time. Only `window = 'dev'`, only `eligible = 1`, and only a
  non-NULL `mar` — an eligible trial always has one, since "beats SPY TR" is among the conditions it
  passed, so a NULL here means a row that cannot be compared rather than a row that compares badly.
  `None` when the method has no eligible dev trial at all. `TRANSITIONS` already carried the
  `('dev-eligible', 'promoted')` edge; no schema or trigger changed.


### lab: the hard gate (lab-hard-gate phases 1-2; D11-D13 hardgate-variant-and-blend-kin)

`lab/hardgate.py` is the rule `lab promote` refuses on, and the only thing in the lab that can stop
a counted test-window look being spent on a method the evidence has already judged. It opens no
research store, runs no backtest, writes nothing and spends no look: it is two SQL reads and
arithmetic on curves already in `trials.curve_json`. Measured 2026-10-09 on the committed lab:
**0.807s** for all seven dev-eligible methods, inside `lab status`.

- **Why it exists.** Five out-of-sample results, five failures — M0021, M0029, M0022 and M0002 on
  `beats SPY TR`, and M0032 losing 415 million rupiah to a deposit-matched SPY. The surviving
  dev-eligible ideas are all cousins of the methods that produced those failures. A lab that keeps
  promoting cousins of disproven families is not learning, and the dev gate cannot see it: a
  twenty-year average and a deflated Sharpe both said yes every time.
- **The rule**, both halves required:
  - **(F) folds** — the method beat the recorded `REF-SPY-HOLD` benchmark in a **majority** of its
    scoreable walk-forward folds (`walkforward.Record.majority`), **and** it is scoreable on every
    fold the geometry yields, at least `MIN_FOLDS = 4`. The second clause is the fail-closed
    answer to thin evidence: under a coin-flip null a strict majority of an *odd* fold count is a
    coin flip at every odd count (n=3 → 0.5000, n=4 → 0.3125, n=5 → 0.5000), so a minimum of 3
    would admit evidence strictly weaker than 4. It is a bound, not a p-value — overlapping folds
    are not independent observations and nothing here may be fed into a DSR. The table is
    `COIN_FLIP_NULL`, in the module.
  - **(F, D11) the promoted variant's own folds** — the picks' record says whether the lab's way
    of *choosing* works out of sample; the look and the money are spent on one variant,
    `store.best_dev_eligible` (the very call `prereg.promote_method` makes, via
    `hardgate.promoted_variant`). `hardgate.variant_record(conn, method_id, candidate_id, geo=None)`
    scores that variant alone through the same `walkforward.evaluate`, handed a mapping of one —
    same de-funding, benchmark, geometry and price rule (D10). It too must be scoreable on every
    fold and win a strict majority. Both halves are required: M0044's picks win 3 of 4 but
    `M0044-TV14-N21`, its only eligible variant, wins 1 of 4; M0053's own variant wins 3 of 4 but
    its picks win 2 of 4. Silent when `best_dev_eligible` names nothing (`promote_method` refuses
    with its own message one line later).
  - **(K) kin** — no method in the candidate's **`family` ∪ its transitive ancestors through
    `parent_id`** reads `test-failed`. Measured across the lab's 63 methods: `family` alone blocks
    26 and misses M0030, whose family is clean but whose parent M0029 and grandparent M0021 both
    failed; ancestors alone block 10; the union blocks 29; the full connected component blocks 36
    in one 26-method blob and is rejected as too blunt — "cousin of a disproven family" stretched
    four hops through unrelated families stops being a statement about the evidence.
  - **(K, D12) blend ingredients** — `hardgate.ingredients(conn, method_id)` reads every `<MNNNN>`
    allocator id out of the method's dev trials' recorded `trials.config_text` (`registry._canon`
    writes every allocator, top-level and nested, a blend's parts and blends of blends included),
    keeps only ids that name a `methods` row, and drops the method itself. Each ingredient, plus
    its own `family` ∪ ancestors (`_lineage`), joins the kin — one hop, every dev variant, nothing
    new stored. This closes the M0028 gap: its `BLEND-RM` runs `M0007-N20-RAW`, whose family's
    M0022 test-failed, yet shared no `family` or `parent_id` with it. Measured on 75 methods it
    moves kin-blocked from 29 to 31 (M0024 via M0011, M0028 via M0007) and refuses nobody new
    today; the whole gate refuses 10 of 10 dev-eligible methods.
  - **(D13) the buy signal follows** — `lab walkforward` already passes `hardgate.failed_kin` to
    `walkforward.buy_signal` (D9), so the signal's kin condition widens with D12;
    `walkforward.py` is untouched. Its `BUY_CONDITIONS` text still says "family union ancestors",
    and the signal does not apply D11 — both left for the owner.
- **Where it is enforced, and where it is not.** `commands/lab.py:_promote` calls it **before**
  `prereg.promote_method`, so a refusal leaves the repository and the database byte-identical: no
  file, no status move, no insight, no analysis row. `lab test` does **not** re-check (K): a
  pre-registration is a promise and is not re-opened, and refusing at `lab test` would strand a
  method in `promoted`, a state with only two exits and both final. What `lab test` adds instead is
  one printed note when the kin has failed since the promotion — a sentence, not a gate, the same
  shape as `_ratchet_warning`.
- **No override exists, in any form.** No `--force`, no flag, no "promote anyway". If the rule
  proves too strict the answer is a recorded, argued change to the rule, because an override
  path is precisely the mechanism that produced the 0-for-5 roster.
- **A missing benchmark refuses**, naming `REF-SPY-HOLD`, so the reader knows it is the lab's
  fixture that is wrong rather than their method. With no benchmark curve there is no fold
  geometry, and "no scoreable folds" is refused rather than waved through.
- **Every curve is de-funded before it is measured.** `trial_deposits(conn, row, curve)` moved here
  out of `commands/lab.py` so the gate, `lab regime` and `lab walkforward` share one de-funding
  path. Every trial from M0032 on is funded with the owner's 5,000,000 IDR a month; measuring a
  raw funded curve against a benchmark that received none read as seventy to eighty points a year
  of edge that was the owner's own deposits (insight 72, 75).
- `check(conn, method_id) -> None` raises `store.LabError`, which `commands/lab.py:run` already
  turns into exit 2 — no new `except` anywhere. It is silent for every status but `dev-eligible`.
  `summary(conn, method_id, geo=None) -> str` is the one-line fold record `lab status` prints
  beside each dev-eligible method, in the shape `"3 of 4 folds; M0044-TV14-N21 alone 1 of 4 folds; kin clean"`
  (the middle clause, D11, only when the picks' record was scoreable and a variant would be
  pre-registered); it is lenient and
  returns the reason as text rather than raising. `fold_summary` is the strict twin the
  pre-registration calls, because a pre-registration must never record a number it could not
  compute. `geometry(conn)` cuts the folds from the benchmark once, for a caller judging many
  methods.
- **What it costs today, measured 2026-10-09.** It refuses all seven dev-eligible methods, which is
  the intended effect and not a side effect. It is not a permanent stop: M0034 and M0035 each win 3
  of 4 folds with clean kin, and read `rejected` only because the bars moved under them.

In `lab status`, `_hard_gate_states` runs the gate once per command over the dev-eligible methods
and catches every `LabError`, so a lab with no benchmark — a new one, or any fixture in
`test_lab_status.py` — prints the refusal as a sentence instead of failing the command. Promoted
methods are not re-judged there: the promise is not re-opened.


### lab: per-trial provenance and comparability (trial-reproducibility)

Two inputs make a re-run of a recorded trial the same measurement and no `trials` column carries
them: the **starting capital** and the **price data**. Both are now recorded, once per trial, in an
added table — `trials` itself is still append-only and was not touched.

- **`trial_provenance`** (`lab/store.py`, schema 5): `trial_n` (primary key, foreign key to
  `trials.n`), `initial_idr` (TEXT, NOT NULL), `price_fingerprint` (TEXT, NULL = unknown),
  `source` (`'recorded'` | `'backfill'`), `measured`. Held append-only by
  `trial_provenance_no_update` and `trial_provenance_no_delete`, the `trial_funding` precedent.
  Surface: `store.ProvenanceRow`, `store.insert_provenance()`, `store.provenance_of()`.
- **Written in the trial's own transaction.** `runner.run_method` and `runner.run_test` insert a
  `source='recorded'` row beside every trial inside the same `BEGIN IMMEDIATE`, with the capital
  the run was actually given (passed to `dev.run_registry(initial_idr=...)` explicitly) and
  `ResearchData.price_fingerprint`. `lab.seed` writes a `source='backfill'` row for each of the 54
  seed trials of a fresh database (20,000,000 IDR, the P7a price fingerprint): P7a ran before the
  lab, so those are a stated fact about that run, not something the run wrote.
- **Back-filled by migration 4 -> 5**, `source='backfill'`, for every trial without a row. Capital
  by a rule that is exact on all 152 trials of the committed lab — checked with
  `git merge-base --is-ancestor d79fc83 <git_sha>` over its 26 distinct shas: no `trial_funding`
  row (trials #1..#128, all before `d79fc83`) -> 20,000,000; a `trial_funding` row (#129..#152,
  all after) -> 10,000,000. Price fingerprint by the known map: `5451195f…`, `e597367b…` and
  `399d0d25…` -> `5451195f…` (proven: the current store's four price files hash to it); the test
  store `56e83810…` -> itself; anything else (the test store `bbe7abfb…`, whose file map is not
  on this machine) -> NULL.
- **`research.price_fingerprint_of(files)`** is `fingerprint_of` over the price files only
  (`bars.csv`, `dividends.csv`, `fx.csv`, `unserved.csv`), and `ResearchData.price_fingerprint` is
  it for a loaded store. The whole-store `fingerprint` still moves when `fundamentals.csv` is added
  or refreshed; the price fingerprint does not. Use the store fingerprint to reproduce a method
  that reads the fundamentals panel, the price fingerprint to compare recorded curves.
- **`runner.recorded_capital(conn, n) -> Decimal`**, beside `recorded_contributions`. It raises
  `store.LabError` for a trial with no provenance row rather than guess. `lab remeasure` (dev and
  seed paths) and `lab costs` pass it to `dev.run_registry(initial_idr=...)`; `lab remeasure`
  refuses, before loading any store, a set of trials recorded at two different capitals
  (`remeasure.plan_capital`: one `run_registry` call runs one capital);
  `hardgate.trial_deposits` divides a deposit by it, not by the live `INITIAL_IDR`, so the next
  change to that constant cannot silently mis-de-fund every funded trial the gate reads.
- **The comparability rule** — decision **(D10)** in `lab/hardgate.py`'s module docstring.
  `hardgate.fold_record` — hence `check`, `fold_summary` and `summary` — refuses with
  `store.LabError` when the `REF-SPY-HOLD` benchmark trial's price fingerprint (the row
  `hardgate.benchmark_n` names and `Geometry.bench_n` carries), or any of the method's dev
  trials', is unknown or differs from the benchmark's. Fail closed, no override. The check itself
  is `hardgate.mismatches(conn, bench_n, rows)`, one sentence per incomparable trial;
  `hardgate.comparability(conn, method_id, geo)` is that check over exactly the rows the gate
  scores. The report-only commands reuse `mismatches` through
  `commands/lab.py:_comparability_warnings`: `lab walkforward` and `lab regime` print one
  `WARNING` line per such method and carry on. `lab run` calls `hardgate.pin_dev_store` and
  refuses, before any backtest, a dev store whose price fingerprint differs from the benchmark
  trial's or is unknown (the benchmark comparison is skipped only on a database with no benchmark
  trial, which the gate refuses anyway). The key is deliberately **not**
  `trials.store_fingerprint`: keyed on it, the rule would have refused every promotion, because the
  benchmark was recorded on `5451195f…` and every M-method on `399d0d25…` or `e597367b…` with the
  same prices.
- **What it cost, measured 2026-10-09 on the committed lab.** 0 trials stranded, 0 verdicts
  changed, `lab status` byte-identical (`Promotable now: (none)`); `lab remeasure M0007`, `M0011`
  and `H-P7A` (54 of 54, six metrics within `METRIC_TOL`, trades exact) reproduce on today's store
  with `INITIAL_IDR` at 10,000,000. At 10M without the recorded capital the same 54 all diverged.
- **Deliberately not done.** The moments those re-runs recover were not written to the committed
  lab. With them, `H-P7A-F9` becomes re-evaluable (`rejected` -> `dev-eligible` through
  `lab reevaluate`) and `M0007-N20-RAW` reads DSR 0.978 (from 0.952), `M0011-RAW20-TV14-N21`
  0.973 (from 0.943). No status moves by itself; the judgement is the explore loop's (insight of
  2026-10-09, "Old results stopped matching because the starting amount changed, not the prices").

### lab: the N policy for the luck gate (lab-luck-gate phase 1)

`lab/npolicy.py` holds the answer to "N what?" in the deflated Sharpe the lab's luck gate applies.
It is pure — it reads a lab SQLite connection, writes nothing, and touches no clock, filesystem or
network. Phase 4 of the `lab-luck-gate` plan set wired the gate to it: `store.gate` is its one
caller, it is always passed a policy name explicitly (never `DEFAULT_POLICY`), and the name the
lab ships is `store.DSR_POLICY`.

- **Why it exists.** `backtest.dev.deflated_sharpe` assumes `n_trials` *independent* trial Sharpes.
  The lab hands it one per dev `trials` row, and those rows are not independent: measured over the
  month-end equity curves already stored in `trials.curve_json`, the mean pairwise correlation across
  the dev trials is 0.612 and the participation ratio of their correlation matrix is 2.338, over 102
  common month-ends. Deflating by the row count therefore asserts an independence the data
  contradicts, and overstates the hurdle.
- `Policy` / `POLICIES`: the three named answers, and what each measures on the committed
  `lab/lab.sqlite` — `all-trials` = **126**, `methods` = **28**, `effective` = **2**.
  - `all-trials` — one look per dev trial row, the literal reading of the design and what the lab
    **did until 2026-10-08**. Deliberately **unfloored**, so an empty lab reads 0 rather than a
    fabricated 2.
  - `methods` — **in force since 2026-10-08** (lab-realistic-gate R1). One look per distinct method
    with a dev trial, floored at the measured participation
    ratio: `max(distinct_methods, ceil(participation_ratio))`. Counts a family of variants as the one
    idea it is, while the floor guarantees the policy can never claim fewer independent looks than
    the curves measurably show. The floor does not bind on the committed database (ceil(2.34) = 3
    against 28 methods); `NCount.floored` says when it does.
  - `effective` — the participation ratio alone, rounded, floored at `DSR_MIN_N = 2` (below two
    trials the deflated Sharpe is undefined). The honest count of independent *return streams*, and
    for that reason not a count of how many times the search looked: every lab strategy holds US
    large-cap equities, so the streams collapse onto the market factor. Kept live so the gate's
    sensitivity stays inspectable.
- `DEFAULT_POLICY = "methods"` — deliberately the policy the lab actually ships
  (`store.DSR_POLICY`; it was `"all-trials"` until 2026-10-08), so a caller that forgets to name one
  cannot be deflated by an N the gate does not use. It moves whenever that constant moves, and only
  then — `test_the_policy_names_are_a_closed_set` now asserts it as an **equality to
  `store.DSR_POLICY`** rather than as two literals, so the next move of the lever cannot separate
  the two silently, with the literal kept beside it so that a move is still a deliberate edit.
- `effective_n(conn, policy=DEFAULT_POLICY) -> NCount`: the N and the evidence behind it. `NCount.n`
  is the int to hand `dev.deflated_sharpe`; the rest is why — `trial_rows`, `distinct_methods`,
  `participation_ratio`, `mean_pairwise_corr`, `curves_used`, `month_ends`. `NCount.basis` is a
  **one-line, newline-free** evidence string, shaped for the one-line fields it is destined for
  (`docs/lab/prereg/MNNNN.md` and `web/data/lab.json`'s `gate.dsrNBasis`); `NCount.evidence()` is the
  fuller sentence that also repeats `n` and the policy name. `UnknownPolicy(ValueError)` for a name
  outside `POLICIES`; `check_policy(name)` is the standalone validator.
- `correlation(conn) -> Correlation` / `participation_ratio(conn) -> float`: the measurement, from
  the curves the database already holds — it spends no test-window look and runs no backtest. The
  participation ratio is `(sum L)^2 / sum L^2` over the eigenvalues of the correlation matrix of the
  trials' monthly returns: 1 when every curve is the same curve, N when they are mutually
  uncorrelated, and clamped to that range because floating point on a near-singular matrix can step a
  hair outside either end. Curves are aligned on the month-ends common to *every* one of them, so
  each row is the same months measured the same way; a curve that is short, unparseable,
  non-positive or perfectly flat is dropped rather than correlated. Fewer than two surviving curves
  gives `participation_ratio = 1.0` and `mean_pairwise = None` — one look is still one look — rather
  than an exception, because the module must never raise on data it only reads.
- `dev_method_count(conn) -> int`: distinct `method_id` over `window = 'dev'` trials.
- **The numbers above age; the test of them does not.** `tests/test_lab_npolicy.py` used to pin the
  committed-database measurements as four `COMMITTED_*` constants, which meant every new dev trial
  falsified the test — so it had been given a `skipif` that quietly switched it off once the lab
  outgrew 110 trials, leaving the module unchecked against the only database it is ever run on.
  Those constants are gone. `_reference_correlation` now recomputes the participation ratio and the
  mean pairwise correlation straight from the raw `trials.curve_json` rows and asserts the library
  agrees to `|delta| < 1e-12`: the pin is the arithmetic, not the answer, so growth in the lab can
  no longer age it out. On the lab as committed that is 126 dev + 2 test = 128 rows, ratio
  2.338473061106947, rho 0.6124884723866705.

### lab: the derived verdict (lab-luck-gate phase 4)

A dev trial's eligibility is **decided when it is asked for**, not read back off the row. `trials`
is append-only, so a recorded `dsr`, `eligible` and `failed` name the bars in force on the run
date; the lab's two owner-set bars both moved on 2026-10-07, and a leaderboard that mixes bars
cannot be read. `lab/store.py` owns the whole of it — the two constants, the derivation, and the
one write path that acts on it.

- **The two constants, and nothing else decides the gate.** `DSR_MIN` is the threshold (0.95 ->
  0.90, the owner's stated risk appetite, Decision D1) and `DSR_POLICY = "methods"` is the
  single name that decides N (Decision D2; `"all-trials"` until 2026-10-08, moved by
  lab-realistic-gate R1 because counting one look per variant *run* made re-running one method
  perturb every other method's verdict — N = 28 on the committed database, not 126). Moving either
  constant moves published verdicts without rewriting a row: R1's move took `dev-eligible` from 2
  to 8 and `rejected` from 27 to 21 (M0002, M0007, M0011, M0019, M0024 and M0030 crossed), with
  `trials` still 128 rows and `test_looks` still 2. The two constants are also guarded differently
  in prose, and deliberately: `tests/test_lab_gate_wording.py` sweeps the documents an unattended
  session acts on for a **stale threshold**, because a threshold is a number a document can state
  and get wrong, and it compares what it finds against `DSR_MIN`. A policy is a *name* with no
  number to compare, so it is swept instead by
  `test_the_gate_text_is_built_from_the_constants_that_decide_the_verdict`, which requires the live
  `DSR_POLICY` to appear rather than forbidding the dead one. Prose that still describes N as the
  row count was corrected where it states a live rule (`prereg.gate_text`'s docstring,
  `docs/lab/prereg/README.md`, the explorer skill); extending the wording guard to policy names is
  recorded as larger work than a constant move rather than half-done. There is no policy over the threshold and no second
  place either number is written. `DSR_LABEL` is **derived** from `DSR_MIN`
  (`LUCK_LABEL_PREFIX + f"{DSR_MIN:.2f}"`), so the label and the threshold can never disagree.
- `is_luck_label(label) -> bool`: true for a luck-test failure label recorded under *any*
  threshold the lab has used. Recognising the luck label by `label == DSR_LABEL` stops working the
  moment `DSR_MIN` moves — the recorded rows say `"DSR >= 0.95"` — and a luck-only rejection would
  then read as an owner failure and could never be reconsidered. The five P7a D8 labels are never
  of this shape, so the prefix is an exact discriminator. Every reader uses this.
- `recorded_labels(failed) -> tuple[str, ...]`: a recorded `failed` string split into its labels.
  **History, not a verdict** — use it to show what the lab said at the time, never to decide what a
  trial is today.
- `OWNER_INPUTS_LABEL` / `owner_failures(trial) -> tuple[str, ...]`: the five P7a D8 conditions the
  row misses *as they read now*, in `dev.FAILURE_LABELS` order. **Four re-derived, one carried.**
  `beats SPY TR`, `max DD`, `PF` and `trades` are thresholds over columns `trials` already records,
  so they are recomputed from those columns against the live `tuning.MAX_DRAWDOWN`,
  `tuning.MIN_PROFIT_FACTOR` and `dev._MIN_TRADES` — the same comparisons `dev.py` makes, on the
  same values. `owner inputs` is carried from the recorded string, because it is the one condition
  that is not a threshold: it asks whether a human hand-picked a parameter of the *candidate*,
  there is no column to recompute it from, and no constant re-decides it. It takes the **row**, not
  the string, so a trial recorded under the 15% drawdown bar is read against today's.
- `sr_star(n_trials, var_trials) -> float`: `dev.deflated_sharpe`'s own hurdle line, isolated so it
  can be asked for at an N no trial was ever run at. The formula being inverted, not a second
  opinion about it.
- `recover_dsr(*, sharpe_daily, dsr_at_run, n_at_run, var_trials, n_trials) -> float | None`: a
  recorded DSR re-evaluated at `n_trials` looks. `DSR = Phi((SR - SR*(N)) * k)` and `k` does not
  depend on N, so `k` is recovered by inverting a known DSR at the N it belongs to and the answer
  is the same `Phi` with a different `SR*`. **At `n_trials == n_at_run` it returns `dsr_at_run`
  exactly, for any `var_trials`** — which is what makes it a *re-reading* of the record. Monotone
  in N above a half, which is the ratchet as arithmetic. `None` where the inversion is undefined
  (fewer than two looks at either N, non-positive `var_trials`, a non-finite input, a DSR of
  exactly 0 or 1, or an SR sitting exactly on the hurdle).
- `dev_sharpe_variance(conn) -> float | None`: the sample variance of the dev trials' daily
  Sharpes **as the lab stands now** (`None` below two), the same expression `runner.trial_rows`
  deflates by.
- `dsr_at(conn, trial, n_trials) -> float | None`: the trial's DSR at `n_trials` looks, by two
  routes — exactly from `trial_moments` when phase 2's `lab run` or phase 3's `lab remeasure`
  recorded them, otherwise by inverting the recorded `dsr` through `recover_dsr`. **Both routes
  deflate by `dev_sharpe_variance(conn)` and never by the `var_trials` recorded beside the trial**
  (Decision D12): the variance is read once, before the branch, so the two cannot drift. The
  deflated Sharpe asks how extreme a Sharpe is against the maximum of N draws from the
  trial-Sharpe distribution, and *both* N and that distribution must describe the search as it is
  today — pairing today's N with a frozen variance would mix bars one column over. The recorded
  `var_trials` stays in `trial_moments` as history. `None` when the recorded `dsr` is NULL, which
  is the 54 P7a seed rows by construction.
- `Gate(n, policy)` / `gate(conn, policy=None) -> Gate`: the luck bar in force right now. The
  threshold is deliberately not in it — that is `DSR_MIN`, one constant. `gate` memoises per
  (database file, policy, dev trial set): `npolicy.effective_n` eigendecomposes 110 month-end
  curves, and `lab status` asks for a verdict once per method. The key is content-derived — a
  `sqlite3.Connection` has nowhere to hang a cache and nothing safe to key on — and because
  `trials` is append-only, `(row count, highest trial number, distinct methods)` pins the dev trial
  set exactly, so the cache is self-invalidating. In-memory databases are never cached. A caller
  judging many trials should still resolve it once and pass `at=`.
- `pending_gate(conn, method_id, pending, *, policy=None) -> Gate`: the gate a batch of `pending`
  new dev trials will be judged under. The batch is not in the database yet and `trials` is
  append-only, so the count is projected forward *in the unit the policy counts in*: `all-trials`
  gives N + `pending` (exactly `dev_trial_count(conn) + len(results)`, the expression
  `runner.trial_rows` used before the policy existed), `methods` gives N + 1 only for a method with
  no dev trial yet, `effective` gives N, and an unrecognised name gives N + `pending`, the most
  punishing of the three. Every branch returns at least `gate(conn).n`.
- `Verdict(dsr, failed, eligible, n, policy, derived)` / `verdict(conn, trial, *, at=None,
  policy=None)`: the trial's eligibility as it reads now. **Nothing is returned verbatim** — the
  four threshold conditions come from `owner_failures`, `owner inputs` is carried, and the luck
  test is decided on `dsr_at(conn, trial, g.n)`, this trial's DSR **at the gate's current N**,
  never at the N it happened to be run under. Re-thresholding only when `n_trials_at_run` already
  equals the gate's N is explicitly superseded: it would admit a candidate for having been tried
  *earlier*, which is the defect the phase exists to remove. **A DSR that cannot be evaluated
  fails the luck test**, the same rule `runner.trial_rows` applies to a new trial whose DSR comes
  back `None` — `derived` is False exactly then, and `dsr` is `None` with it. `failed == ()` is
  `eligible`, always. `policy` exists for a read-only comparison; the write paths never pass it.
- `best_dev_eligible` is unchanged in contract and now judges on `verdict(...).eligible` rather
  than the frozen `eligible` column, so two trials recorded six weeks apart are ranked against the
  same bar. The ordering is still MAR then `n`, and selection is still **never** on DSR. It takes
  `at=` / `policy=` and resolves the gate after the rows are fetched, so a method with no
  comparable dev trial costs no estimator read.
- `REEVALUATION_MARKER`, `Reevaluation(method_id, status_before, status_after, moved, gate,
  unblocked, derived, unjudgeable, dev_trials)`, `reevaluate_method(conn, method_id)` and
  `reevaluate(conn, method_ids=None)`: the one write path that reconsiders a verdict, behind the
  single new `('rejected','dev-eligible')` transition and the independent `_blocking` check. The
  CLI section above has its rules, its refusals and its output; the caller holds the transaction,
  as every other writer in this module does.
- `runner.trial_rows` is a two-line delta onto this: `n_trials` is `store.pending_gate(conn,
  method.id, len(results)).n` instead of `dev_trial_count(conn) + len(results)`. `n_trials_at_run`
  still records **the N the DSR was computed at**, which is what it has always meant, and the
  variance is still the sample variance across every recorded dev trial plus the batch — only the
  *count* of looks is policy-dependent, never the dispersion the expected maximum is drawn from.
  Since lab-realistic-gate R1 the two **diverge**: under `methods` a batch of variants of a method
  the lab already holds projects to the lab's current N (it adds 0), and a brand-new method adds
  exactly 1, while `dev_trial_count` keeps climbing by one per candidate. So a reader of
  `trials.n_trials_at_run` must stop treating it as a row count — it is the gate's N on that run
  date, and that is the only thing `remeasure` may reproduce it from. `test_lab_runner.py` asserts
  the projection against `store.pending_gate` and the row count separately, so the two cannot be
  conflated again.
- **Imports stay inside the functions.** `store.gate` imports `lab.npolicy` inside itself, and
  `owner_failures` / `dsr_at` / `_blocking` import `backtest.dev` and `backtest.tuning` inside
  themselves, so `import store` — which the whole lab does — still drags in neither the estimator's
  curve arithmetic nor the backtest package, and no module-scope cycle is closed.

### paper (P4)

`seer_engine.paper` is nightly paper trading. Every module but `store.py` is pure (no psycopg,
requests, yfinance, clock or randomness), `Decimal`-only for money, and covered by the purity tests.
Each night function steps exactly one session the way a runner's loop body does, and its tests prove
that looping it equals the runner (`run_backtest`, `run_book`, `buy_and_hold`) over hundreds of
synthetic sessions.

- **`paper.roster`**: the roster builder (D1, D4; roster-promotion-pipeline R2, D2, D3). Pure: no database, no clock, no I/O, and it imports nothing from `store`. A roster entry is a `strategies` row plus the live Python object the row names; this module is the only place that turns one into the other.
  - `BENCHMARK_ID = "SPY"`, `F4_ID = "F4-MOM12-N20-TREND"`, `F1_ID = "F1-SPY-SMA200-M"`, `FND_ID = "FND"` (phase 6), `BENCHMARK_OBJECT = "buy_and_hold"`. The Gotrade-fee rebuild (017) adds the six ids that trade — `BENCHMARK_GT_ID = "SPY-GT"`, `C_GT_ID = "C-GT"`, `RMW_GT_ID = "RMW-FR-GT"`, `RAW_GT_ID = "RAW-FR-GT"`, `MOM_GT_ID = "MOM-FR-GT"`, `MVW_GT_ID = "MVW-FR-GT"` — plus `BRACKET_GOTRADE_RULES_ID = "design-v0-gotrade"` (named here only; `rules_for` raises `UnknownRules` if it is not a `sim.rules` preset) and `BENCHMARK_SYMBOL = "SPY"`, split off from `BENCHMARK_ID` because that constant is an *entry id* and there are now two benchmark entries while the *symbol* is and always was SPY. `Engine = Literal["bracket", "book", "benchmark"]` and `Status = Literal["active", "retired"]`, with `ENGINES` / `STATUSES` as the `CHECK`s in Python. `Basis = Literal["test-passed", "owner-override"]` with `BASES` (lab-luck-gate phase 6) is the admission vocabulary — two words and no third; `lab.store.PROMOTION_BASES` is the same tuple on the lab's side of the bridge, and `tests/test_paper_roster.py` checks they agree.
  - Errors, all `RosterError(LookupError)` and all naming **the strategy id and the offending value**: `UnknownObject` (`object_name` is not a `RESOLVER` key), `UnknownRules` (`rules_id` is not a `sim.rules` preset), `BadRosterRow` (bad engine or status, missing or surplus fields). None is ever swallowed — a row that cannot be built stops the whole build, because skipping it would leave an unfillable hole in that portfolio's equity curve.
  - `RosterEntry` (frozen dataclass), one paper portfolio: `id, name, sub, icon, is_champion, is_benchmark, sort` (the display fields of the row), `engine: Engine`, `rules: TradeRules | None`, `obj: Strategy | Allocator | None`, `object_name`, `params`, `registry_id: str | None`, `lookback: int`, `gate_note: str`, `gate_applicable: bool = True` (P6; false only for `C`), plus the lifecycle fields `status: Status = "active"` and `paper_end: date | None` (migration 006) and the admission record `lab_provenance: LabProvenance | None = None` (lab-luck-gate phase 6). `rules_id` is a property (`None` for the benchmark).
  - `LabProvenance(method_id, candidate_id, lab_status, basis, reason)` (frozen; lab-luck-gate phase 6, R4/D3): where an entry came from in `lab/lab.sqlite` and on what basis it was admitted. `method_id` / `candidate_id` name a row of the lab's append-only `trials` table — the exact backtest the entry *is*. `lab_status` is the method's status **at the moment of admission**, frozen there: the lab's status machine moves forward only, so a method admitted at `rejected` and later re-judged still *was* `rejected` when the roster took it. `basis` is `test-passed` (the lab's own route, design §3) or `owner-override` (the roster's), and `__post_init__` refuses a non-empty-string field, a basis outside `BASES`, and — the point of the type — an `owner-override` with a blank `reason`.
  - `LAB_PROVENANCE: dict[str, LabProvenance]` — **the second code-side table, and for the same reason as `RESOLVER`**: a promoted `strategies` row carries `promoted_from` (the method id) and nothing else, and this module **must never import the lab** (the `FUNDAMENTAL_PARAMS` argument: a lab-side edit would silently re-digest a started paper strategy). So the roster states its own provenance in its own file, and `tests/test_paper_roster.py` — where importing the lab is free — checks every line against the committed database. Keyed by roster id; an entry with no recorded lab candidate has **no key** (`SPY` the benchmark, `C` the LLM strategy, and `A`, which predates the lab — `H-A` records the idea but has no trial, and `H-P7A-REF`'s `REF-A-V0` is a reference run, not an admission basis). Append only, and never edit a started entry's line to make it read better: the field says what was true on the night.
  - The admission rule, stated (lab-luck-gate D3): passing a gate has never been this roster's criterion and still is not — `FND` joined having failed its M0005 dev-window gate, and `RMW-FR` trades while `M0022` reads `rejected`. The method lab's design reads the other way (§3 and §6 both put a test pass on the path to this roster); **that divergence is deliberate**, because paper trading is how a near-miss earns the right to be taken seriously and the lab's gate is tuned for the money decision. A lab test pass is a *sufficient* basis for a paper entry, never a necessary one. Every current lab-derived entry is therefore an `owner-override` with its reason: `F4` / `F1` and their `-FR` twins (`H-P7A-F4` / `H-P7A-F1`, the yardsticks, each failing max DD and never test-looked), `FND` (`M0005-ALL`, the a-priori blend chosen before the numbers), `RM-FR` (`M0011-RAW20-TV14-N21`, DSR 0.897 at N = 90 — it failed only the luck test; retired for `RMW-FR` before its first session) and `RMW-FR` (`M0022-W-TV16`, DSR 0.916 at N = 110, likewise). 017's four successors (`RMW-FR-GT`, `RAW-FR-GT`, `MOM-FR-GT`, `MVW-FR-GT`) each carry their predecessor's **same** method, variant and `lab_status`, re-stated with the fees named: the trial behind the admission did not change, only what the paper entry pays.
  - `Binding(obj, params=None, from_registry=False)`: what an `object_name` resolves to — the live object and where its params come from (`from_registry` means the row's `registry_id` names the `backtest.registry` candidate that supplies them, as F4 and F1 have always worked).
  - `RESOLVER: dict[str, Binding]` — **the one code-side table, and the extension point** (D2): `buy_and_hold` → no object, `STRATEGY_A`, `STRATEGY_C`, `FACTOR`, `TIMING` and (phase 6) `FUNDAMENTAL` → `Binding(obj=FUNDAMENTAL, params=FUNDAMENTAL_PARAMS)`. A database cannot hold an `Allocator`, and `eval`-ing an import path out of a row would make `strategies` a code-execution surface, so a row carries a stable *name* instead. Keys are forever: a stored spec names one, so renaming a key would move a live digest. Append only. `resolver_names() -> tuple[str, ...]` (sorted); `resolve(object_name) -> Binding` (`UnknownObject`, never a default and never `None`).
  - `rules_for(rules_id) -> TradeRules | None`: the `sim.rules` preset, the same object (so `is DESIGN_V0` holds); `None` → `None` (the benchmark trades under no rule set); an unknown id raises `UnknownRules`.
  - `Row` (Protocol): what `from_row` reads off a `strategies` row — `id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id, object_name, registry_id, gate_note, gate_applicable, status, paper_end`, at the column types, nullables included. `paper.store.StrategyRow` satisfies it structurally, which is how `roster` stays pure. `RosterRow` is the same thing as a plain frozen dataclass, used by the seeds and the tests.
  - `from_row(row) -> RosterEntry`: one row, through `RESOLVER`. Validates engine and status against the `CHECK`s, resolves the object and the rules, requires a non-empty `gate_note`, and enforces the shape rules — a `benchmark` row carries no object, rules or `registry_id`; a `bracket` / `book` row needs a `rules_id` and an object; a `from_registry` object needs a `registry_id` (checked against `REGISTRY` for allocator and rules identity) and any other object must have `registry_id` NULL. `lookback` comes from the object (`obj.lookback` for bracket, `obj.lookback(params)` for book, 1 for the benchmark). `lab_provenance` is `LAB_PROVENANCE.get(row.id)` — keyed by roster id, not read off the row, because `strategies` has one provenance column (`promoted_from`) and no room for the rest, and this module may not open `lab/lab.sqlite` to fill it in; an id with no key gets `None`, correct for `SPY`, `C` and `A` and caught for anything else by the test that pins which ids must carry one. There is no path that returns `None` or a half-understood entry.
  - `from_rows(rows) -> tuple[RosterEntry, ...]`: every row as an entry, sorted by `(sort, id)`, raising on the first row it cannot build and refusing duplicate ids. All or nothing — no row is ever dropped.
  - `SEED_ROWS: tuple[RosterRow, ...]`: every row `003_paper.sql` through `017_roster_real_fees.sql` writes, as data, in `sort` order — the six entries that trade (`SPY-GT`, `C-GT`, `RMW-FR-GT`, `RAW-FR-GT`, `MOM-FR-GT`, `MVW-FR-GT`) first, then the thirteen the rebuild and its predecessors retired (`SPY`, `A`, `F4`, `F1`, `C`, `FND`, `F4-FR`, `F1-FR`, `RM-FR`, `RMW-FR`, `RAW-FR`, `MOM-FR`, `MVW-FR`, each carrying `status="retired"`). `tests/test_paper_roster.py` checks it equals a migrated database's `strategies` rows.
  - `OWNER_FUNDING: dict[str, str]` (017): the owner's funding plan as the roster's own statement of it — `amount_idr "5000000"`, `cadence "monthly"`, `day_of_month "25"`, on top of `PAPER_INITIAL_IDR`. **Written out here rather than imported from `sim.contributions`**, for the `FUNDAMENTAL_PARAMS` reason: anything this module imports becomes an input to a started strategy's spec digest. `tests/test_paper_roster.py` — where importing the backtest side is free — pins it equal to `sim.contributions.OWNER_MONTHLY`, so the two cannot drift in silence.
  - `PRE_FUNDING_IDS: frozenset[str]` (017): the thirteen entries digested before the funding plan was modelled. `spec` leaves `funding` out for exactly these and includes it for every other entry — stating the *exemption* rather than the inclusion, so a future promoted entry carries its funding plan by default and cannot be born without it. **Closed; never append to it**: an entry funded by some other plan needs a second funding dict saying what that plan is, not an exemption that says nothing.
  - `BENCHMARK_COST_MODEL: dict[str, CostModel]` and `benchmark_cost_model(entry_id) -> CostModel` (017): what a benchmark entry's fills pay. A benchmark row carries no `rules_id` (`from_row` refuses one), so there is no column for the lever and no `TradeRules` to read it off — it is stated here, and unlike `LAB_PROVENANCE` it **is** part of `spec`, because a yardstick that quietly changed what its fills cost would turn "beats SPY TR" into a different comparison without moving a digest. `SPY` keeps `"flat"` forever (retired, started flat, digest pinned); `SPY-GT` is `"gotrade"`. The lookup **never defaults**: an unnamed id raises `BadRosterRow` and stops the night rather than producing a flattering comparison.
  - `ROSTER: tuple[RosterEntry, ...] = from_rows(SEED_ROWS)` (all nineteen entries; `active(ROSTER)` is the six `-GT` ones), `ROSTER_IDS`, `MAX_LOOKBACK_BARS = max(e.lookback for e in ROSTER)` (still 253, FACTOR's `factor_lookback` — FND's lookback is 20, the dollar-volume window, since a filing's availability is its `filed` date and not a bar count, so phase 6 does not widen the night's market window; a property of `SEED_ROWS`, not of whatever a live database holds). The compiled roster and the stored roster therefore travel the *same* builder, so the pinned digests prove the data path and not just a literal. `C` (P6): `C · News veto`, icon `gavel`, sort 5, engine `bracket`, rules `DESIGN_V0`, `obj = STRATEGY_C`, `params = STRATEGY_C_PARAMS`, gate note "Backtest gate: not applicable (LLM strategy, design §1 item 5)". `FND` (phase 6): `FND · Fundamentals`, "Top 20 by SEC filing factors, monthly", icon `book-open`, sort 6, engine `book`, rules `monthly-hold`, `object_name = "FUNDAMENTAL"`, `registry_id` NULL, `promoted_from = "M0005"`, and a `gate_note` that states the gate it **failed** (M0005's dev window only, fundamental coverage 0.3151: beats SPY TR +1.8% vs +351.4%, 15 closed trades against ≥ 100, DSR 0.006 against ≥ 0.95). `gate_applicable` stays true — the gate applies to it and it did not pass; saying so is the point.
  - `FUNDAMENTAL_PARAMS = FundamentalParams(rank="composite", top=20)` (phase 6): FND's parameters, written out in `roster.py` and deliberately **not** imported from `lab.methods.m0005_fundamental_factors`. That module's `source_sha` is frozen in `lab/lab.sqlite`, so editing it for a lab reason would silently re-digest a started paper strategy; the roster says what it runs, in its own file. `composite` is the a-priori equal-weight blend of the four factor families the method's sources name, chosen *before* the numbers — not `M0005-VAL`, which merely had the highest return of six failed dev-window trials and would be a pick made on the multiple-testing noise the lab's `trials` table exists to count. `tests/test_paper_fnd.py` pins it value-equal to the lab module's `COMPOSITE`, because a drift between them would make the promoted row's stored digest and the roster's recomputed digest differ and `store.check_digest` would refuse FND's second night with a `SpecMismatch`.
  - `active(entries=ROSTER) -> tuple[RosterEntry, ...]`: the entries still trading (`status == "active"`), in order. A retired entry keeps every row it ever wrote and its leaderboard place; it only stops trading.
  - `entry(strategy_id) -> RosterEntry`: the seeded roster entry; `KeyError` when it is not on the roster.
  - `rules_dict(rules: TradeRules) -> dict[str, str | None]`: every `TradeRules` field, in field order, as plain strings — minus a lever still at its pre-pin default (`sim.rules.is_pinned_default`), so a roster strategy that does not use a newly added lever keeps the spec digest already written to its live `strategies.params` row.
  - `spec(e) -> dict[str, Any]`: the frozen spec (C2 `params.spec`), JSON-ready, strings and nulls only: `id`, `engine`, `object` (the `RESOLVER` key), `object_id`, `registry_id`, `registry_digest`, `rules_id`, `rules`, `params`, `initial_idr`. `status`, `paper_end`, `gate_note`, `gate_applicable` and `lab_provenance` are deliberately **not** in it: retiring a strategy, correcting a note, or recording why an entry was admitted must not move a live digest. Two keys are **conditional**, for the same reason the levers in `sim.rules.LEVERS_SINCE_PINS` are — a fact added after a digest was pinned must not move it: `funding` (`OWNER_FUNDING`) is present for every entry outside `PRE_FUNDING_IDS`, and a `benchmark` entry's `params` state what its fills cost as `cost_rate` while it is flat and as `cost_model` once it is on Gotrade's schedule, so the retired `SPY`'s spec text is unchanged to the byte.
  - `spec_text(s) -> str`: the canonical text of a spec: JSON with sorted keys, no whitespace, ASCII only.
  - `spec_digest(s) -> str`: sha256 (hex) of `spec_text(s)` in UTF-8. Every entry's digest is pinned in `tests/test_paper_roster.py` (`PINS`, checked against `ROSTER` and against the rows read back from a migrated database). 017 added six digests and moved none of the thirteen that existed before it — not the retired `SPY`'s, although 017 moved `is_champion` and `is_benchmark` off it, because neither flag is in the spec.
  - `backtest_gate(e) -> dict[str, Any]`: C2 `params.backtest_gate`, `passed` false for every entry, with `e.gate_note`; for `C` also `"applicable": false` (the web shows "Not applicable" and counts it as not passed). Not part of the spec, so no digest depends on it.
  - `strategy_params(e) -> dict[str, Any]`: the whole `strategies.params` jsonb (`spec`, `digest`, `backtest_gate`), as `paper` writes it.
- **`paper.bracket`**:
  - `BracketNight(session, portfolio, events, snapshot)`: one settled session of a bracket strategy.
  - `settle_bracket(pf, session, bars, splits, last_bar_date, *, rules=DESIGN_V0) -> BracketNight`: settle `session` exactly like one `run_backtest` iteration (`apply_split` per applied split, `sim.step`, `close_unpriced` for symbols whose bars ended, snapshot replaced).
  - `decide_bracket(pf, strategy, params, history, members, data_date, *, rules=DESIGN_V0) -> SizingResult`: the pending orders for `next_session(data_date)`: `strategy.picks` on `history` cut at `data_date`, then `size_picks`.
  - Both take the **entry's own** rule set from the night (`rules=e.rules`), never a module constant: `C` settles and decides at `DESIGN_V0`, `C-GT` at the Gotrade bracket preset, which is what makes the daily-trading control pay the fees it exists to measure.
- **`paper.book`**:
  - `BookNight(session, book, targets, splits, fills, trades, dividends, rejected, forced, snapshot)`: one settled session of a book strategy.
  - `decide_book(market, allocator, params, rules, data_date, held, *, force=False, last_rank=None, marks=None) -> tuple[tuple[Target, ...] | None, bool]`: the targets for `S = next_session(data_date)` and whether the idle residual was appended; `backtest.book_runner._with_idle` and `_rescaled` are reused by import. On a RANK session (`force`, i.e. the kickoff or the nightly preview, or `is_rank_session(rules, S)`) the allocator ranks as `run_book` does and `last_rank`/`marks` are not read. On a RESIZE-ONLY session of split-cadence rules (`rules.resize_cadence`, `is_resize_session`) with `last_rank` given, the allocator is called the same way but only its total weight is used: `_with_idle(_rescaled(market, last_rank, wanted, held - idle, data_date, marks))`. `last_rank` is the last rank session's targets without the idle row (`rank_basket`), `()` when that rank chose nothing; `marks` is `{p.symbol: p.mark for p in book.positions}` of the same book (a `ValueError` when missing on a resize-only session). Otherwise `(None, False)` without calling the allocator, including a resize-only session with `last_rank` None (no rank yet, as in `run_book`). Without a `resize_cadence` nothing is resize-only, so the result is the rank-or-nothing decision it always was. The nightly `paper` command passes both for split-cadence rules (paper split cadence, phase 2): `last_rank` read back from the `book_targets` of `last_rank_session` through `rank_basket`, `marks` from the settled book.
  - `needs_kickoff(rules, paper_start, session, kickoff) -> bool`: rank once on the first session when no kickoff is stored, `session` is not a rank session (`is_rank_session`; a resize-only session counts as not ranking, since there is no basket to rescale yet) and no rank session lies in `[paper_start, session)`.
  - `last_rank_session(rules, paper_start, kickoff, session) -> date | None`: the latest session in `[paper_start, session)` that ranked (`is_rank_session` or the stored kickoff), i.e. `run_book`'s `last_rank` variable read off the calendar; its stored targets are the basket a resize-only `session` rescales. None when nothing ranked yet.
  - `rank_basket(targets, idle_symbol) -> tuple[Target, ...]`: a rank decision's stored targets as `decide_book`'s `last_rank`, with the trailing idle row (`_with_idle`'s residual) taken off; an idle-symbol row anywhere but last is a `ValueError`.
    - **The `MarketAware` branch** (phase 6): an allocator that satisfies `strategies.allocator.MarketAware` (it defines `prepare_market`) is decided through `targets_prepared(prepare_for(allocator, replace(market, history=history)), …)` — `run_book`'s own prepared dispatch, brought to the nightly decision — instead of `allocator.targets(history, …)`. It must be: such an allocator reads part of the `Market` that the `history` dict cannot carry, so the history-only path is not a worse answer but a fixed empty one (`FUNDAMENTAL` finds every symbol ineligible and returns `()`, forever, while every log line says it decided). The `Market` handed over carries the same `history` cut at `data_date`, so no bar dated after `data_date` is reachable on either path, and the panel needs no cut of its own: `panel.as_of(symbol, d)` answers from facts with `filed <= d` and `filed` **is** the no-look-ahead boundary (`005_fundamentals.sql`). The branch is keyed on the protocol and nothing else, so for every allocator without `prepare_market` the expression is byte-identical to before and the five pre-FND strategies replay bit for bit.
  - `deposit_book(book, amount_usd) -> Book`: the owner's deposit into a book, raising **cash and equity together** — `sim/book.py` sizes from equity, so cash alone would leave the book permanently under-deployed. The nightly step calls it with `store.apply_contributions`'s return before settling the session.
  - `settle_book(book, session, bars, targets, idle_added, rules, dividends, splits, last_bar_date) -> BookNight`: `sim.apply_book_split` per applied split (targets rescaled too), `sim.step_book`, `close_book_unpriced` for gone positions, snapshot replaced.
- **`paper.benchmark`**: `buy_and_hold` one session at a time. Whole shares at the first session's open; dividends with an ex-date after the start credited on the ex-date and reinvested at that close; marked at every close.
  - `SPY = "SPY"`; `BenchmarkState(start, cash, equity, position: Position | None, last_session, cost_model: CostModel = "flat")`. The cost model rides in the state, so an entry started under one schedule keeps paying it on its thousandth night; an unknown value is a `ValueError`.
  - `start_benchmark(cash0, start, *, cost_model="flat") -> BenchmarkState`: the benchmark the night before `start`: `q(cash0)` in cash, nothing held.
  - Fees (fee rebuild, phase 3): the entry buy, every dividend reinvestment and the fee each `Fill` records all come from one private `_buy(price, shares, cost_model)`, priced off the same unrounded price, so the recorded fee is the fee inside the cash that moved (`-cash_usd - cost_usd == q(price * shares)`). Under `"flat"` that is the 0.1% it always was and nothing moves. **Wired by 017**: `store.load_benchmark` takes the model as a keyword and `commands/paper.py` passes `roster.benchmark_cost_model(e.id)`, so `SPY-GT` pays Gotrade's measured schedule while the retired `SPY` keeps flat.
  - `split_benchmark(state, factor, session) -> tuple[BenchmarkState, Decimal]`: rewrite the SPY holding in post-split units (floor shares, cash in lieu returned, prices ÷ the exact factor).
  - `step_benchmark(state, session, bar, dividend, *, split=None, deposit=Decimal(0)) -> tuple[BenchmarkState, Snapshot, tuple[Fill, ...]]`: step through `session` (which must be `next_session(state.last_session)`); a `split` runs `split_benchmark` first. `deposit` (017) is the owner's contribution landing on `session`, **spent at that close through the same buy the dividend path uses** — which is what `backtest.benchmark.buy_and_hold` does with it, and this stepper exists to track that curve session by session. A yardstick that banked the deposits as idle cash would drift below the dollar-cost-averaged SPY it is supposed to be, and `paper check` would mismatch on every session after the first deposit. Both land as cash at that close and are spent by one buy, but only the dividend is recorded as `income_usd`: a deposit is the owner's own money, not something the holding earned. A negative `deposit` is a `ValueError`; the default of zero is every session that receives none, and the whole history before the funding plan existed.
- **`paper.replay`**: the pure comparison behind `paper_check`.
  - `Engine`, `Status = "ok" | "mismatch" | "split-affected" | "not-started"`; field tuples `SNAPSHOT_FIELDS`, `ORDER_FIELDS`, `POSITION_FIELDS`, `FILL_FIELDS`, `TRADE_FIELDS`, `TARGET_FIELDS`, `HOLDING_FIELDS`; `MAX_SHOWN = 10`.
  - `Holding(symbol, shares, mark)`: the benchmark's holding as `book_positions` stores it. `PaperHead(strategy_id, engine, paper_start, last_session, usd_idr)`: what the replay needs from a started strategy. `Records(...)`: one strategy's paper record, stored or expected (cash, equity, pending, snapshots, orders and marks, positions, fills, trades, targets, holdings). `Difference(where, text)`. `CheckResult(strategy_id, status, sessions, paper_start, last_session, differences, total_differences, splits)`.
  - `sessions_stepped(paper_start, last_session) -> int`; `last_close(market, symbol, on) -> Decimal`; `held_before(fills, session) -> frozenset[str]`.
  - `expected_bracket(market, strategy, params, head, *, rules=DESIGN_V0, contributions=()) -> Records` (`run_rules(rules)` plus the next decision, under the **entry's own** rule set — `DESIGN_V0` for `C`, the Gotrade bracket preset for `C-GT`, so a Gotrade entry is never reconstructed at the flat rate); `expected_book(market, allocator, params, rules, head, dividends, *, contributions=()) -> Records` (`run_rules(rules)` plus every decision; under split-cadence rules a resize-only session is decided from the replay's OWN last rank basket, `rank_basket` of its latest rank or kickoff decision, and marks = each held symbol's `last_close` on `data_date`, never from the stored rows); `expected_benchmark(market, head, dividends, *, contributions=()) -> Records`.
  - `contributions` (017), on all three: the owner's deposits as the **record** of what was credited — `(session, usd)` pairs off `store.read_contributions`, `applied` rows only — never the schedule that produced them. Each stored amount was frozen at the USD/IDR of the session it landed on, so re-deriving it at one rate would disagree with the stored record the first time the rupiah moved. It is `()` for every entry that has received none, which is every entry while paper is paused, and the replay is then bit-identical to what it was before 017. `Records.deposited: Decimal` carries the total beside `initial_cash` (capital on day 0, not capital in); `compare` names the fields it checks and does not check this one — it annotates the stored record rather than being replayed.
  - `expected_book` replays a `MarketAware` allocator through `run_rules(..., prepared=prepare_for(allocator, market))` (phase 6), exactly as `paper.book.decide_book` decided it; `prepared` stays `None` for every other allocator, so the five strategies that already have a paper clock replay byte for byte. The `market` is passed **uncut** here because `run_book` cuts per session itself and `FUNDAMENTAL` indexes its bars by date (`History.index_of`), never by last row — the property `allocatorkit.assert_no_lookahead` pins.
  - `compare(engine, stored, expected) -> tuple[Difference, ...]`: every stored value that differs, snapshots first, `paper_state` last. `split_exposure(engine, paper_start, records, splits)`: the applied splits that hit a held or pending symbol. `judge(head, stored, expected, splits) -> CheckResult`; `not_started(strategy_id)`; `broken(strategy_id, where, message, *, paper_start=None, last_session=None)`.
  - `failures(results, require_sessions) -> tuple[str, ...]`; `exit_code(results, require_sessions) -> int` (1 when `failures` is non-empty); `render(results) -> tuple[str, ...]`.
- **`paper.compare`** (roster-promotion-pipeline phase 3; pure — no database, no clock, no I/O, in `paper/roster.py`'s discipline, with `commands/compare.py` as its one impure edge). Not to be confused with `paper.replay.compare`, which diffs one strategy's stored night against its replay; this module ranks strategies against each other.
  - `MIN_COMMON_SESSIONS = 63` (a quarter of a 252-session year, three full rebalances of a `MONTHLY_HOLD` book), `MIN_RANKED = 2`, `SESSIONS_PER_YEAR = 252`, `YEAR_DAYS = 365.25`, `NA = "n/a"`, `Status = Literal["ranked", "insufficient"]`. `Window`, `Performance`, `Row`, `Comparison` (frozen dataclasses).
  - `compare(series: Mapping[str, Sequence[Any]], *, min_sessions=MIN_COMMON_SESSIONS) -> Comparison`: `series` maps a strategy id to its `(date, equity)` snapshots in date order, the equity anything `float()` accepts, so `equity_snapshots`' `Decimal` rows go straight in. Every id handed in comes back as exactly one `Row` — never dropped. Every ranked figure is computed over **one window shared by every ranked strategy** — the intersection of snapshot dates, not `[max(start), min(end)]`, so every strategy's returns come from the very same consecutive pairs of dates — and that window is returned in `Comparison.window` rather than implied. A strategy whose own curve is shorter than `min_sessions` never joins the intersection; among the rest, while the intersection is still short, the strategy whose removal leaves the longest intersection is dropped (ties: shortest own curve, then id) until it reaches `min_sessions` or fewer than `MIN_RANKED` remain. Everything left out is a `status="insufficient"` row carrying a `reason` — never a ranked row and never a silent omission.
  - The risk-adjusted figure is the **annualised Sharpe** of the session returns at a zero risk-free rate (`mean / stdev(ddof=1) * sqrt(SESSIONS_PER_YEAR)`): defined for any window with two returns and non-zero variance, scale-free so it does not reward merely having run longer, and — because the window is common by construction — estimated from the same number of observations for every ranked strategy. Sortino needs enough losing sessions to estimate a tail; Calmar/MAR divides by max drawdown, which is understated over a short window and exactly `0.0` for a curve that only rises. It is still noisy, so the window and session count travel with every figure.
  - **Inception-to-date is separate** (invariant 6): every row carries an `inception` block over the strategy's own whole curve, with its own start, end and session count. It is never ranked and never mixed into the common-window figures.
  - Fractions, not percents (`total_return`, `cagr`, `max_drawdown` are `0.123` for 12.3%), matching `web/lib/metrics.ts` and `backtest/metrics.py`; CAGR uses Actual/365.25. `render(c) -> tuple[str, ...]` is the table; `as_json(c) -> dict[str, Any]` is the shape the leaderboard's TypeScript port is pinned against.
- **`paper.store`** (impure; nothing commits, `paper` runs a night in one transaction):
  - `BENCHMARK_ID = "SPY"`, `MARKET_WINDOW_DAYS = 550` (the only window constant), `PRICE_QUANTUM`, `DIVIDEND_QUANTUM`. `StoreError(RuntimeError)`; `SpecMismatch(StoreError)`: a frozen strategy's stored digest differs from the code's.
  - Roster rows: `StrategyRow(id, name, sub, icon, engine, rules_id, is_champion, is_benchmark, sort, paper_start, params, status="active", paper_end=None, promoted_from=None, object_name=None, registry_id=None, gate_note=None, gate_applicable=True)` — structurally a `paper.roster.Row`, so `roster.from_rows(read_roster_rows(conn))` is the whole roster-from-data path and neither module imports the other. The migration 006 columns are nullable on rows that are not roster rows; `roster.from_row` validates them with a named error rather than defaulting them.
  - `read_strategies(conn)`, `read_strategy(conn, strategy_id)`; `read_roster_rows(conn)`: every row with `engine IS NOT NULL`, by `(sort, id)`. `engine` is the predicate because it is what the paper night dispatches on and what migration 003 set on exactly the roster's rows. **Retired rows are returned** (only `roster.active` drops them from a night), and a row with an `engine` but an unusable `object_name` is *not* filtered out here — `roster.from_row` raises `UnknownObject` for it, which is the point.
  - Lifecycle (006), the **only two writers** of `status` and `paper_end`: `retire(conn, strategy_id) -> date | None` sets `status = 'retired'` and `paper_end` to `paper_state.last_session` — the last session actually traded, NULL when the strategy never started — and returns it. Re-retiring is a deliberate no-op that returns the stored `paper_end`, so an interrupted swap can simply be re-run; a missing row is a `StoreError`. It reads `paper_state` for the date and nothing else: no `equity_snapshots`, `orders`, `book_*` or `paper_state` row is written or deleted, so a retired strategy keeps its whole track record and its leaderboard place. `set_paper_end(conn, strategy_id, paper_end)` is the repair for a retirement taken by hand SQL: only a retired row whose `paper_end` is still NULL is written, and an active row, a missing row or one already stamped is a `StoreError`. Neither commits — the caller's transaction decides, so a retirement and its replacement's INSERT land together and the board never shows two rosters.
  - `freeze_spec(conn, strategy_id, *, spec, digest, backtest_gate, paper_start)` (writes once); `check_digest(row, digest)` (raises `SpecMismatch`).
  - State: `PaperState(strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr, pending_session, pending_decision)`; `read_paper_state(conn, strategy_id)`; `init_paper_state(conn, strategy_id, *, paper_start, cash0, usd_idr) -> PaperState` (day 0: `last_session = prev_session(paper_start)` plus the day-0 snapshot); `write_paper_state(conn, strategy_id, *, cash, equity, last_session)`; `write_pending(conn, strategy_id, session, *, decision)`; `upsert_snapshot(conn, strategy_id, snapshot)`; `read_snapshots(conn, strategy_id)`.
  - Bracket: `load_portfolio(conn, strategy_id) -> Portfolio`; `insert_pending_orders(conn, strategy_id, placed, companies=None) -> int`; `save_bracket_night(conn, strategy_id, portfolio, events, snapshot)`; `read_orders(conn, strategy_id) -> tuple[tuple[Order, Decimal | None], ...]`.
  - Book: `LoadedBook(book, pending_session, targets, idle_added)`; `load_book(conn, strategy_id, *, idle_symbol=None) -> LoadedBook`; `save_book_night(conn, strategy_id, book, fills, trades, snapshot, *, executed_targets=None)`; `save_book_decision(conn, strategy_id, session, targets)` (an empty decision writes no row); `read_book_positions`, `read_book_targets(conn, strategy_id, session)`, `read_book_fills`, `read_book_trades`.
  - Benchmark: `load_benchmark(conn, strategy_id="SPY", *, cost_model="flat") -> BenchmarkState`; `save_benchmark_night(conn, strategy_id, state, snapshot, fills)`. The fee model is not in `paper_state`, so it comes from the caller — the roster's statement about *this* entry (`roster.benchmark_cost_model`), because a benchmark stepped one night at a time must still be paying Gotrade on its thousandth night.
  - Contributions: `Contribution(strategy_id, due_date, session_date, amount_idr, usd_idr, amount_usd, applied)` — one `paper_contributions` row, with `due_date` the owner's calendar date (the 25th), `session_date` the first NYSE session on or after it, and all three money fields frozen when the row was written. `read_contributions(conn, strategy_id)` (by `due_date`) is the dated cashflow series a money-weighted return integrates over: equity alone cannot say whether a rise was the book growing or the owner adding money. `accrue_contributions(conn, strategy_id, due_dates, amount_idr, *, through, usd_idr_on)` records every deposit that has landed by `through` and leaves an already-recorded one alone, so a backfilled `fx_rates` can never move a stepped book's history. `apply_contributions(conn, strategy_id, session) -> Decimal` stamps that session's rows applied and returns the dollars for the caller to add to the state it is about to step; it deliberately does **not** write `paper_state`, so the deposit is recorded once, carried once and written once by that engine's own `save_*_night`. Crediting an already-stepped session is a `StoreError` rather than a silent rewrite of settled history, and a second call over the same session credits nothing.
  - Market: `dividends_on(conn, session, symbols)`, `dividends_between(conn, start, end)` (`book_runner.DividendMap` shape); `applied_splits_on(conn, session) -> tuple[tuple[str, Decimal], ...]`, `applied_splits_between(conn, start, end)`; `market_window_since(data_date) -> date`; `load_market_window(conn, since) -> Market` (bars via `backtest.io.read_bars_frame(conn, since=...)`, every membership interval, FX).
  - News verdicts (P6): `NewsVerdict(rank, symbol, verdict, reason, model, prompt_version, headlines, earnings_date, decided_at)`; `has_vetoes(conn, strategy_id, session) -> bool`; `write_vetoes(conn, strategy_id, session, verdicts) -> int` (plain INSERTs after validating ranks 1..n, unique symbols, a known verdict and a tz-aware `decided_at`; a duplicate is a database error, so callers check `has_vetoes` first in the same transaction); `read_vetoes(conn, strategy_id, session)` (by rank); `allowed_between(conn, strategy_id, start, end) -> dict[date, frozenset[str]]` (only `allow`, sessions `start..end` inclusive).

### delisting (delisting-stress-roster-rules phase 1)

Read-only survivorship stress. It perturbs an in-memory `Market` and nothing else: it records no lab
trial, moves no N, spends no test-window look and never writes `engine/.research`. A test asserts it
imports neither `lab.store` nor `lab.runner`, so it cannot record a trial even by accident. Its
randomness is a `Random` passed in by the caller, which is why it lives here rather than under
`backtest/` or `sim/` (`tests/test_strategy_purity.py` globs those two paths).

- `WINDOW_START = date(1996, 1, 2)`, `WINDOW_END = date(2015, 10, 16)` (the dev window), `YEAR_DAYS = 365.25`, `MIN_PRICE = 0.0001`.
- `Hazard`: what the store's own membership says about how often a member stopped being priceable — `ever_members`, `served`, `unserved`, `exits`, `served_exits`, `unserved_exits`, `mean_members`, `member_years`, `exits_by_year`.
- `measure_hazard(market, *, unserved=(), window_start=WINDOW_START, window_end=WINDOW_END) -> Hazard`: measured, never assumed. On the committed store this is 5.091%/yr for all exits and 4.002%/yr for unpriced exits, over 10,096 member-years.
- `Exposure`: one priced survivor's member-time — when it was both an index member and priceable.
- `survivors(market, *, window_start=..., window_end=...) -> tuple[Exposure, ...]`: the priced members that never left the index inside the window, sorted by symbol. These are what a run injects deaths into.
- `Death(symbol, last_bar)`: one injected delisting; the symbol is gone the session after `last_bar`.
- `draw_deaths(market, exposures, hazard_per_year, rng) -> tuple[Death, ...]`: who dies and when, under a constant annual hazard, `P(death) = 1 - exp(-hazard x years)`.
- `kill(market, deaths, delisting_return, *, decline_sessions=1) -> Market`: a **new** `Market` in which every named symbol is delisted on its death date at return `r`. `decline_sessions > 1` spreads the loss over that many sessions instead of making it abrupt.
- `stressed(market, exposures, *, hazard_per_year, delisting_return, rng, decline_sessions=1) -> tuple[Market, tuple[Death, ...]]`: one Monte Carlo draw.

### dividends (P4)

- `AMOUNT_QUANTUM = Decimal("0.000001")`, `CASH_TYPES = frozenset({"CD", "SC"})`, `CURRENCY = "USD"`.
- `Dividend(symbol, ex_date, amount)`.
- `quantize_amount(value) -> Decimal`: rounded half-up to 6 decimals (`numeric(14,6)`).
- `parse_massive(raw) -> Dividend | None`: one Massive `/v3/reference/dividends` row, or None for a valid row Seer does not credit (other types or currencies).
- `totals(items) -> list[Dividend]`: one per (symbol, ex_date), the exact sum quantized half-up to 6 dp.
- `adjust_for_splits(items, split_items) -> list[Dividend]`: put freshly fetched dividends into the units of the bars fetched with them.
- `upsert_dividends(conn, items) -> int`: insert new dividends and update changed ones; returns how many rows changed.

### llm (P4)

- `ANTHROPIC_VERSION = "2023-06-01"`, `DEFAULT_TIMEOUT_S = 20.0`, `DEFAULT_RETRIES = 1`, `DEFAULT_BACKOFF_S = 2.0`, `DEFAULT_MAX_TOKENS = 400`, `MAX_ERROR_BODY = 200`.
- `LlmError(RuntimeError)`: a request failed after retries, or the reply held no text.
- `LlmConfig(base_url, api_key, model)` (`api_key` excluded from `repr`); `load_config() -> LlmConfig | None`: None when any of `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` is unset or empty.
- `messages_url(base_url) -> str`: the Messages endpoint for `base_url`. `scrub(text, secret) -> str`: key/token query parameters and every occurrence of `secret` redacted.
- `Client(cfg, *, transport=None, timeout=20.0, retries=1, backoff=2.0, max_tokens=400, sleep=time.sleep)`; `Client.complete(system, prompt, *, temperature=None, thinking=None, max_tokens=None) -> str`. The key goes out as both `x-api-key` and `Authorization: Bearer` (z.ai compatibility). `veto` (P6) and `explain` (why-this-pick-pipeline) both pass `temperature=0.0`, `thinking="disabled"` (sent as `{"type": "disabled"}`) and `max_tokens=1024`, because `glm-5.3` with a small budget spends it on reasoning and returns no text. `explain` and `veto` catch every `LlmError`, so neither raises past it.

### finnhub (P6)

- `BASE_URL = "https://finnhub.io/api/v1"`, `MIN_INTERVAL = 1.0` (s between calls: the free tier's 60 a minute), `DEFAULT_TIMEOUT_S = 15.0`.
- `FinnhubError(message, status)`: a request failed after its retry. The text never holds the key.
- `load_key() -> str | None`: `config.get("FINNHUB_API_KEY")`.
- `Client(key, *, transport=None, base_url=BASE_URL, min_interval=MIN_INTERVAL, timeout=DEFAULT_TIMEOUT_S, retries=1, backoff=2.0, clock=time.monotonic, sleep=time.sleep)`; the key travels only in the `X-Finnhub-Token` header. One retry on a connection error, a timeout, 429 or 5xx (honouring a longer numeric `Retry-After`, capped at 60 s); anything else raises `FinnhubError`. Calls are spaced from the end of the previous attempt, retries included.
  - `company_news(symbol, start, end) -> list[Headline]` (`GET /company-news`; symbols in the dot form `bars` stores, e.g. `BRK.B`); items with a missing or non-integer `id` or `datetime`, or an empty headline, are dropped. No cutoff here: `veto` applies `select_headlines`.
  - `earnings(symbol, start, end) -> date | None` (`GET /calendar/earnings`): the earliest date in `[start, end]`, else None. For `BRK.B` the free tier returns the `BRK.A` row.

### P4 additions to existing modules

- `massive.Client.dividends(d)` (and the `MassiveSource` protocol): one call per fetched session, `/v3/reference/dividends?ex_dividend_date=D` (the free tier served 513 rows for 2026-09-18 in one page); USD cash dividends of types CD and SC, following `next_url`.
- `splits.apply_splits` also rewrites `dividends` before the execution date: `round(amount * split_from / split_to, 6)`.
- `commands/nightly.py`: fetches and stores dividends for every missing session in its one transaction, and adds paper-held symbols (`universe.paper_symbols(conn, d)`) to each session's wanted set, so a position keeps its bars after its symbol leaves the index.
- `universe.paper_symbols(conn, d) -> set[str]`: symbols paper state still needs a bar for on session `d`: pending or open `orders`, every `book_positions` row (the SPY benchmark holding included), and `book_targets` decided for `d` or later.
- `runs`: `start_paper(conn, run_id)`, `finish_paper(conn, run_id)` and `fail_paper(conn, run_id, error)` set `paper_status`, `paper_error` (redacted, cut like `error`) and `paper_finished_at` on the real run row.
- `sim.apply_book_split(book, symbol, factor, session, rules, targets=None) -> BookSplit` (`sim/book.py`, exported from `seer_engine.sim`): the book engine's split rule. Shares × factor (floored for whole-share rules); cash in lieu credited to cash and the position's `income_usd`; stop, take, mark and entry price ÷ the exact factor; floor-to-zero closes as `forced` at the old mark; pending targets for the symbol rescaled. `BookSplit(book, targets, in_lieu, trade, fills)`. Called only for splits recorded with `applied = true`.
- `backtest.io.read_bars_frame(conn, *, since=None)`: `since` limits the `COPY` to `date >= since`. The default is unchanged, so every existing caller and `load_market` are byte-identical.

### sean (Sean phases 1 and 4)

`sean.ledger` is pure: no database, no network, no clock, no floats. It is the Python twin of
`web/lib/sean/ledger.ts` (plan contract B). Both must reproduce `web/lib/sean/fixtures/ledger.json`,
so a change to one is a change to both.

- `Order(id, symbol, side, executed_at, price, shares, total_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd)`:
  the `sean_orders` columns the ledger reads. `side` is `buy` or `sell`, `executed_at` must be
  timezone-aware, money fields must be `Decimal`, and `shares > 0`. `.trade_date` is the New York
  calendar date of the fill (a 03:10 WIB fill belongs to the previous US session). `.fees_usd` is
  trading + regulatory + PPN.
- `Holding(symbol, shares, cost_usd)`, `Ledger(holdings, realized_usd, fees_usd)`, and
  `PnlPoint(day, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd)`, whose
  fields are exactly the `sean_equity` columns.
- `Closes = Mapping[str, Sequence[tuple[date, Decimal]]]`. Helpers: `money()` (cents, half away
  from zero), `share_count()` (9 decimals), `order_from_mapping()`, `closes_from_mapping()`,
  `sort_orders()` (by `executed_at`, then `id`), `close_on_or_before()`.
- `build_ledger(orders) -> Ledger`, `pnl_series(orders, days, closes) -> list[PnlPoint]` (days
  strictly ascending, else `ValueError`), `pnl_at(orders, d, closes)`.
- The method is average cost with fees in the cost basis. A sell is clamped to the shares held,
  and a sell of a stock never seen bought changes only the fees. A position under 1e-9 shares is
  closed. Each holding is valued at its last close on or before the date, else at its last order
  price. Money is rounded only on output.

`sean.marks` (impure: Yahoo and psycopg):
- `CloseFetch = Callable[[str, date, date], list[tuple[date, Decimal]]]`.
- `yahoo_closes(symbol, start, end, *, downloader=None)`: split-adjusted daily closes in
  `[start, end]` through `yahoo.download`.
- `fetch_closes(starts, end, fetch=yahoo_closes) -> Fetched(closes, missing)`. It never raises for
  a symbol, and skips a start after `end`. `Fetched.rows()` gives `(symbol, date, close)` rows.
- `upsert_marks(conn, rows) -> int`: one `unnest` INSERT with `ON CONFLICT (symbol, date) DO UPDATE ... WHERE ... IS DISTINCT FROM`,
  so an identical re-run writes 0 rows. It does not commit.
- `read_marks(conn) -> dict[str, list[(date, close)]]`, dates ascending.

`sean.equity` (impure: psycopg):
- `read_orders(conn) -> list[Order]` in ledger order. `symbol_starts(orders)` gives
  `(symbol, first trade date)` sorted by symbol.
- `series(orders, end, closes)` gives one point per `dates.sessions(first trade date, end)`, or
  `[]` with no orders.
- `lock(conn)`: `EXCLUSIVE` on `sean_marks` and `sean_equity`. It blocks other writers but not
  readers, so the site reads the previous series until commit.
- `replace_equity(conn, points) -> int`: `DELETE FROM sean_equity`, then insert every point. No
  commit. The series is recomputed in full on every run, because a deleted or late upload changes
  history.

`commands.sean.execute_marks(conn, *, now_utc=None, dry_run=False, fetch=marks.yahoo_closes) -> int`
is the testable body of `sean marks`. `tests/test_sean_command.py` injects `fetch`.

`sean.calibrate` (Sean phase 7; pure except `rows_from_db`):
- `PaidFees(ref, on, side, symbol, amount, trading, regulatory, ppn)` is one receipt. `on` is a
  WIB `date` (not a datetime), and every money field must be a non-negative finite `Decimal`.
  `.total` sums the three fee parts.
- `Residual(paid, expected, current)`. `.gaps` is paid minus expected per part, `.gap` is the
  largest absolute gap, and `.ok` means `gap <= TOLERANCE` (`Decimal("0.01")`).
  `.expected_total` sums the expected parts.
- `Calibration(since, residuals)`. `.current` holds the orders on or after `since`, `.misses`
  holds the current ones not `ok`, and `.passed` means there are no misses.
- `current_since()` returns `costs.GOTRADE.current.since`.
- `check(paid, *, since, fee=costs.fee_parts)` replays `fee(side, amount, on=p.on)` over every
  order and keeps their order.
- `format_report(cal)` gives one line per order and a closing sentence, in plain words.
- `wib_date(at)` returns the WIB date of an aware datetime, and raises `ValueError` on a naive
  one. `rows_from_db(conn)` reads `sean_orders` in `executed_at, id` order.

`lab.real_costs` (Sean phase 7). Only `measure` runs the engine, and only `journal` writes:
- `REAL_COST_SINCE = 31`, `FLAT = "flat"`, `REAL = "gotrade"`, `REPRO_TOL = 1e-9`.
- `requires_real_cost(method_id)` is True for M0031 and later.
- `real_cost_problem(method) -> str | None` names every variant that is not a book rule set at
  `cost_model="gotrade"`, and says which `*_GOTRADE` preset to build on. `runner.preflight` raises
  it as `LabError`.
- `resolve_method(id) -> (Method, Path)`. `pick_candidate(conn, method, candidate_id=None) ->
  (Candidate, trial row)` picks the best dev trial by MAR (ties go to the lower `n`, and a trial
  with no MAR ranks last).
- `twins(candidate) -> (flat, real)`.
- `measure(method, candidate, trial, data) -> Comparison` makes one `dev.run_registry` call on
  the dev window only. It is built from two `Side`s (`side_of`), and `.reproduced` checks the
  recorded side against the trial's total return.
- `format_report(cmp)` is the terminal report. `insight_text(cmp) -> (title, body)` is the plain
  journal text.
- `journal(conn, cmp) -> insight id` is one `store.add_insight(kind="observation")`, and the
  caller owns the transaction.

## Migration 002 (`db/migrations/002_engine.sql`)

This migration is additive only. It is written by the engine, and web does not read these tables.

- `universe(symbol, index_id IN ('SP500','NDX'), start_date, end_date NULL, source_symbol)`, with PK `(index_id, symbol, start_date)`, `CHECK end_date > start_date` and an index on `symbol`. When an interval spans a rename, `source_symbol` joins the source tickers with `/`, oldest first (`FB/META`).
- `split_adjustments(symbol, execution_date, split_from > 0, split_to > 0, applied, recorded_at)`, with PK `(symbol, execution_date)`.
- `backfill_log(symbol PK, status IN ('ok','empty','failed'), first_date, last_date, rows, error, updated_at)`.
- `runs_real_session_uidx`: a unique index on `runs(session_date) WHERE NOT is_demo`, which allows at most one real run per session.

## Migration 003 (`db/migrations/003_paper.sql`, P4)

Additive only: new columns are nullable or defaulted, `orders` keeps every type and constraint.

- `strategies` gains `engine` (`bracket` | `book` | `benchmark`), `rules_id` (`design-v0`, `monthly-hold`, NULL for SPY) and `paper_start` (the first paper session; NULL until `paper` starts it). `params` holds the frozen spec, its digest and `backtest_gate`.
- `orders` gains `mark` (an open order's last close, in the order's own pre-split units).
- `runs` gains `paper_status` (`running` | `success` | `failed`), `paper_error` and `paper_finished_at`.
- `paper_state(strategy_id PK, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr, pending_session, pending_decision, updated_at)`: one row per paper strategy.
- `book_positions(strategy_id, symbol)` PK: `sim.book.Position` (fractional-capable `shares`, `mark`, entry date and price, `days_held`, episode `cost_usd` / `income_usd`, stop, take, `exit_pending`). The SPY benchmark's holding is a row here too.
- `book_targets(strategy_id, session_date, symbol)` PK, unique rank: a book strategy's ranked decision for one session, kept after execution, with `explanation`.
- `book_fills` (`seq` within a session, side, reason `entry`…`forced`) and `book_trades` (closed holding episodes, `idle` flag, exit reasons `signal`, `time`, `gap`, `tp`, `sl`, `forced`; index on `(strategy_id, exit_date)`).
- `dividends(symbol, ex_date)` PK, `amount` > 0: Massive cash dividends (CD + SC summed), in bars' units; `splits.apply_splits` rewrites them with the bars.
- Data: the four roster display rows (upsert; `SPY` is the only champion and the benchmark), and `B`/`C` deleted only when no `orders` or `equity_snapshots` row references them.
- Applied to Neon on 2026-10-04 (runbook ship check).

## Migration 004 (`db/migrations/004_news_veto.sql`, P6)

Additive only.

- Data: the `C` roster row (`C · News veto`, "A's picks, LLM can veto on news", icon `gavel`, sort 5, engine `bracket`, rules `design-v0`, not champion, not benchmark), as an upsert: 003 had deleted the old unreferenced `C` row.
- `news_vetoes(strategy_id → strategies, session_date, rank ≥ 1, symbol, verdict IN ('allow','veto','failed'), reason, model NULL when unset, prompt_version, headlines jsonb [{id, datetime, source, headline}] newest first, earnings_date, decided_at timestamptz)`, PK `(strategy_id, session_date, symbol)`, unique `(strategy_id, session_date, rank)`. One row per candidate checked; `paper` and `paper_check` read it, the LLM is never re-asked. About 0.55 MB a month.
- Demo-owned: `demo.DEMO_TABLES` includes `news_vetoes`. `paper`'s orphaned-rows guard does not count it (verdicts exist before C starts).
- Applied to Neon by the nightly `Migrate` step on the first scheduled run after the merge; that night also starts C's clock.

## Migration 006 (`db/migrations/006_roster.sql`, roster-promotion-pipeline phase 1)

Additive only, to 003's discipline: every new column is nullable or defaulted, nothing is dropped,
no `CHECK` is narrowed, migrations 001–005 are untouched. Written by the engine; web reads `status`
and `paper_end` from the leaderboard.

- Lifecycle: `strategies` gains `status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired'))` (a retired row keeps its history and stops trading), `paper_end date` (the last session actually traded; NULL while active) and `promoted_from text` (the lab `methods.id` the row came from, when it was promoted).
- Definition, read by `paper.roster.from_row`: `object_name text` (a `paper.roster.RESOLVER` key), `registry_id text` (a `backtest.registry` id for book entries, else NULL), `gate_note text` (the display fact the go-live checklist reads) and `gate_applicable boolean NOT NULL DEFAULT true`.
- Data: the five rows 003 and 004 inserted are backfilled with the four definition values, byte-for-byte `paper/roster.py`'s `SEED_ROWS`; `tests/test_paper_roster.py` checks that equality against a migrated database. The five spec digests do not move — none of these columns is in the spec.
- Why a name and not an import path: a row cannot hold an `Allocator`, and `eval`-ing an import path out of the table would make `strategies` a code-execution surface. A name the resolver does not know is a hard error when the roster is built, never a silently dropped portfolio.
- Replacing a horseman is therefore a transaction, not a code edit: INSERT the new row, set the old row's `status` to `retired` and its `paper_end` (`paper/store.py`'s `retire` is the engine-side writer of that transaction). Retirement never deletes `equity_snapshots`, `orders`, `book_*` or `paper_state` rows and never clears `paper_start`, so the leaderboard keeps the whole track record and can say the row is retired rather than hiding it.

## Migration 007 (`db/migrations/007_fnd.sql`, roster-promotion-pipeline phase 6)

Additive only, in `004_news_veto.sql`'s shape: one roster display row, no column added, dropped or
narrowed, and no existing row touched. It requires 006, whose columns it names.

- Data: the `FND` roster row (`FND · Fundamentals`, "Top 20 by SEC filing factors, monthly", icon `book-open`, sort 6, engine `book`, rules `monthly-hold`, `object_name = 'FUNDAMENTAL'`, `registry_id` NULL, `gate_applicable` true, `promoted_from = 'M0005'`, not champion, not benchmark), as an upsert. Every value is byte-for-byte `paper/roster.py`'s `FND` seed row, which is what `tests/test_paper_roster.py`'s migration-equality test compares.
- **Why a migration when phase 5's `promote` writes the same row**: the two write it to different databases. `promote --method M0005 --candidate M0005-ALL --id FND --lab-status-stays` wrote it to the live Neon instance, whose roster is already data; this file writes it to every database brought up *from* migrations — CI's throwaway schema, a fresh local train database, a rebuilt Neon — so `paper`'s `plan_night` finds a `strategies` row for every roster entry.
- **No frozen spec, no `paper_start`, no paper clock** is written here: `paper` writes them on the first night through `store.freeze_spec`, exactly as it did for SPY, A, F4, F1 and C. A row with no `paper_start` is a strategy that starts on the next night — phase 2's path, and FND is its first user.
- **The definition columns are not optional**: `from_row` reads them, and a NULL `object_name` raises `UnknownObject` while a missing `gate_note` raises `BadRosterRow` — either of which stops the whole paper night. So the file writes all four.
- `status` is deliberately **not named**, so the `ON CONFLICT` branch cannot resurrect a strategy someone has since retired (006 defaults it to `active`, which is what FND wants). `promoted_from` is written on INSERT and never on UPDATE, so re-running the file can never clobber what `promote` wrote.

## Migration 009 (`db/migrations/009_evidence.sql`, why-this-pick-pipeline phase 2)

Additive only: `evidence jsonb` (nullable) on `orders`, `book_targets` and `book_previews`. The value is a JSON array of plain-English strings, the facts the method's formula used on that symbol the night it was decided. NULL means no evidence: rows written before 009, the idle symbol, or a night whose evidence function raised (Paper logs it and still stores the decision). `paper/store.py` writes it through keyword-only `evidence=` arguments of `insert_pending_orders`, `save_book_decision` and `save_book_preview`. It never enters `paper.replay.Records` or `compare`, so `paper_check` is unaffected. Readers: `explain` (orders, book_targets) and the web (all three, through `to_jsonb(row) -> 'evidence'` so a query also works before 009 is applied).

## Migration 017 (`db/migrations/017_roster_real_fees.sql`, GOTRADE_FEE_REBUILD phase 12)

Data only, in `007_fnd.sql`'s shape: six roster rows inserted, thirteen retired, no column added,
dropped or narrowed.

- **Why.** Every entry on the roster assumed a flat 0.1% a side. `sim/costs.py` is fitted to 30 of the owner's own Gotrade receipts and reproduces both sides of his 2026-10-07 activity to the cent; measured through `costs.fee_parts`, a round trip costs 2.500% at $10, 1.036% at his current $28 slot, 0.620% at $50 and 0.493% at $5,000 — 12.5x, 5.2x, 3.1x and 2.5x the 0.200% assumed. The asymptote is about 2.5x; everything above it is the $0.10 per-order floor, which binds below roughly $50 an order.
- **Why six new ids and not six edits.** `cost_model` sits in `sim.rules.LEVERS_SINCE_PINS` at its no-op `"flat"`, so moving a **started** entry onto `"gotrade"` changes its frozen spec digest and `store.check_digest` refuses its next night with a `SpecMismatch`. `docs/runbooks/paper-trading.md` states the rule — to change anything about a strategy, add a NEW entry with a NEW id and let its clock start on its own first night — and 010, 011 and 013 are the precedents.
- **Why it was free.** Measured against production before it was written: `paper_state.last_session` was 2026-10-06, `pending_session` 2026-10-07, and **no session had ever been stepped**. A fresh clock therefore threw away no history.
- Data: `SPY-GT` (the benchmark and the champion — the yardstick pays what the methods pay), `C-GT` (the daily-trading control, on the roster permanently by the owner's standing instruction: being expensive is the finding it exists to produce, so it is never retired on cost grounds), and `RMW-FR-GT` / `RAW-FR-GT` / `MOM-FR-GT` / `MVW-FR-GT` — the same four lab methods and recorded variants already on the roster, under `monthly-rank-weekly-resize-frac-gotrade` and `monthly-hold-frac-gotrade`. Every value is byte-for-byte `paper/roster.py`'s `SEED_ROWS`, which is what `tests/test_paper_roster.py` compares against a migrated database.
- The six predecessors are set `status = 'retired'`, **not deleted**: a retired entry keeps every row it ever wrote, including its un-stepped 2026-10-07 decisions (80 `book_targets` rows and 4 `orders`). `is_champion` / `is_benchmark` move to `SPY-GT` and `sort` is renumbered so the six that trade come first; none of those three is in the spec, so no digest moves.
- **No `paper_start`, no `paper_state`, no frozen spec** is written here: the first unpaused night writes them through `store.freeze_spec`, exactly as for every other entry.
- `nightly.yml`'s `PAPER_PAUSED` is still `'true'`, so this migration applies on the next nightly and nothing else happens. Resuming is one commit by the owner, and only by the owner.

## Data Flow

Phase 1 provides the building blocks. Write commands in later phases use them in this order:

1. `cli.main` calls `config.load_env()`, builds the parser from `discover()`, sets up logging and calls the command's `run(args)`.
2. `run` opens `closing(db.connect())`. It does not use `with connect()`, because psycopg's connection context manager commits on exit.
3. `demo.purge_demo_if_needed(conn, args.dry_run)` runs in its own transaction before any other write.
4. Reads (`dates.run_dates`, `universe.*`, `http.get_json` / `fx.fetch_*`) are followed by writes (`bars.upsert_bars`, `fx.upsert_fx`, `runs.*`) inside `with db.transaction(conn, args.dry_run):`.
5. The transaction commits, or rolls back and re-raises. `main` maps exceptions to exit codes.

`veto` (P6) is the one write command that calls the network after reading the database: it reads the
candidates in a transaction it rolls back, makes every Finnhub and LLM call with no transaction open,
then writes all its rows in one short transaction. A network failure becomes a `failed` row, never an
exception. The real night is `migrate` → `nightly` → `veto` → `paper` → `paper_check` → `explain`.

`sean marks` (Sean phase 4) follows the same pattern as `veto`. It reads `sean_orders`, fetches
Yahoo closes with no transaction open, then in one locked transaction upserts `sean_marks`,
re-reads the orders and replaces `sean_equity` whole. In `nightly.yml` it is the last step, after
`explain`, and `continue-on-error`.

## Dependencies

### External
- `psycopg[binary]>=3.2`: the Postgres driver, used for COPY into temp tables in the upserts.
- `pandas>=2.2`, `pandas_market_calendars>=5.0`: the NYSE schedule, including closes, half days and DST.
- `numpy>=2`: indicator math and the float64 arrays in `strategies.base.History` (declared in P3; it was already installed through pandas).
- `requests>=2.32`: HTTP, through one module-level `Session` in `http.py`.
- `python-dotenv>=1.0`: parses `.env.local`. The file is parsed, never `source`d, because it contains an unquoted `&`.
- `yfinance>=1.0`: used only by `yahoo.py` (phase 3 backfill, and P7a's research store through its dividends-aware download with `actions=True`), imported lazily.
- Finnhub REST (P6, no new package: `requests`): `company-news` and `calendar/earnings` on the free tier, 60 calls a minute.
- `scikit-learn>=1.9,<1.10` (P6a): Strategy B's `HistGradientBoostingRegressor`, used only by `strategies.b_model`. The minor version is pinned, because a frozen model is a pickle of its estimator, and `b_model`'s digest reads the fitted trees' private node arrays. It brings `threadpoolctl` (used to cap the threads in the determinism probe), `joblib` and `scipy`. `cli.discover` imports every command, so `backtest_b` makes every command load scikit-learn at startup (about 0.5–1 s); `import seer_engine.strategies` alone does not.
- dev: `pytest>=8`, `pytest-xdist>=3.6` (pytest runs `-n auto` by default, one worker per core; pass `-n0` to run serially), `ruff>=0.16,<0.17` (lint config in `[tool.ruff]`: `py311`, selects `E9` and `F`, ignores `F401`).

### Internal module graph
- `cli` imports `config` and `commands`. `commands.migrate` imports `config` and `db`.
- `db` imports `config`. `demo` imports `db`.
- `prices` imports only the standard library; `bars` imports `prices` and re-exports it. `fx` imports `http` and `bars.to_decimal`. `runs` imports `dates.RunDates` and `http.redact`.
- `http` imports `__version__` for `USER_AGENT`.
- `yahoo` imports `bars` and pandas. `commands.backfill` imports `bars`, `dates`, `db`, `demo`, `fx`, `universe` and `yahoo`.
- `sim.model` imports `prices`. `sim.lifecycle` and `sim.split_adjust` import `dates`, `prices` and `sim.model`. `sim.sizing` imports `dates` and `sim.model`. Nothing in `sim` imports `bars`, `db` or `http`.
- `strategies.*` import numpy, `prices`, `sim` (for `Pick` and `q`) and each other. `backtest.market`, `runner`, `benchmark`, `metrics`, `tuning` and `report` import numpy, `dates`, `prices`, `sim`, `strategies` and each other; `backtest.market` also imports `seer_engine.fundamentals` (`EMPTY_PANEL`, `FundamentalPanel`), which is pure. None of them imports `bars`, `db`, `http` or `config`.
- `backtest.io` imports `config`, psycopg, pandas, numpy and the pure backtest modules. `commands.backtest` imports `config`, `db`, `dates`, `prices`, `universe` (for `BENCHMARK`), `backtest.*` and `strategies.a`.
- `strategies.a2` imports numpy, `sim`, `strategies.a`, `strategies.base` and `strategies.indicators`; never `universe` (psycopg), so `REGIME_SYMBOL` repeats `universe.BENCHMARK` and a test asserts they are equal. `backtest.walkforward` imports `dates`, `strategies.a2`, `strategies.base` and `backtest.runner`, `metrics`, `tuning`, `market` and `benchmark`. `backtest.wf_report` imports `backtest.report`'s helpers (read-only), `dates`, `sim`, `strategies.a` (`ATR_N`, `SMA_N`), `strategies.a2`, and `backtest.metrics`, `runner`, `tuning`, `benchmark` and `walkforward`. None of them imports `bars`, `db`, `http` or `config`.
- `backtest.io` also imports `wf_report` (for `write_wf_report`). `commands.backtest_wf` imports `config`, `db`, `dates`, `universe` (for `BENCHMARK`), `backtest.io`, `walkforward`, `benchmark`, `market`, `metrics`, `runner`, `tuning`, `wf_report`, `commands.backtest` (for `never_fetched_members`) and `strategies.a2`.
- `strategies.b_model` imports numpy, scikit-learn (`HistGradientBoostingRegressor`), `threadpoolctl`, `pickle` and `hashlib`, and nothing from the engine. scikit-learn loads none of psycopg, requests or yfinance, so the module stays pure. `strategies.b` imports numpy, `sim` (`Pick`), `strategies.a` (`_bracket`, `Features`, `DESIGN_PARAMS`), `strategies.base` and `strategies.indicators`. It never imports `b_model`, so `import seer_engine.strategies` does not load scikit-learn, and never `universe` (psycopg), so `SPY_SYMBOL` repeats `universe.BENCHMARK` and a test asserts they are equal.
- `backtest.labels` imports numpy, `dates`, `sim.model` (`TIME_STOP_DAYS`) and `strategies.base`; its `COST` repeats `sim.COST_RATE` as a float, and a test pins them equal. `backtest.b_walkforward` imports numpy, `dates`, `strategies.b`, `strategies.b_model`, `backtest.labels`, `runner`, `metrics`, `market`, `tuning` (`Verdict`) and `walkforward` (`Fold` and the private `_check_folds`, `_day`, `_session`, `_join`, `_GATE_NAMES`, read-only). `backtest.b_report` imports `backtest.report`'s and `wf_report`'s helpers (read-only), `dates`, `strategies.a`, `strategies.b`, `strategies.b_model` (constants), and `backtest.b_walkforward`, `labels`, `metrics`, `runner`, `tuning`, `benchmark` and `walkforward`. None of them imports `bars`, `db`, `http` or `config`.
- `backtest.io` also imports `b_report` and `strategies.b_model` (for `write_b_report` and `write_model_artifact`). `commands.backtest_b` imports `config`, `db`, numpy, `backtest.io`, `b_walkforward`, `b_report`, `walkforward`, `benchmark`, `market`, `metrics`, `runner`, `commands.backtest_wf` (`resolve`, `tune_all`, `run_walk_forward`, `BacktestWfError`), `commands.backtest` (`never_fetched_members`), `strategies.a2`, `strategies.b` and `strategies.b_model`.
- `sim.rules` imports `dates` only (its agreement with `sim.model`'s constants is a test). `sim.book` imports `dates`, `prices` (`Bar`), `sim.model` (`q`) and `sim.rules`. Neither imports `sim.lifecycle` or `sim.sizing`, and nothing in `sim` imports `bars`, `db` or `http`.
- `strategies.allocator` imports numpy, `dates`, `prices`, `sim` (`Pick`, `q`), `sim.book`, `strategies.base` and `strategies.indicators`. It names `backtest.market.Market` under `TYPE_CHECKING` only (for `MarketAware` / `prepare_for`), so there is no runtime `strategies` -> `backtest` import and no cycle. `strategies.f_index`, `f_rotation`, `f_factor` and `f_swing` import numpy, `strategies.allocator` (`target_from_close`, and `month_end_closes` in `f_index`), `strategies.base`, `strategies.indicators` and `sim` / `sim.book`, plus `dates` (`f_index`) or `prices` (`f_rotation`, `f_swing`); none imports another family or `universe`.
- `backtest.book_runner` imports `dates`, `market`, `metrics`, `runner` (`run_backtest`, `RunResult`, `INITIAL_IDR`, read-only), `sim.book`, `sim.model`, `sim.rules`, `strategies.allocator` and `strategies.base`. `backtest.dev` imports `dates`, `tuning`, `benchmark`, `book_runner`, `market`, `metrics`, `runner` (`RunResult`), `sim.rules`, `strategies.allocator` and `strategies.base`. `backtest.dev_report` imports `benchmark`, `dev`, `metrics`, `report`'s helpers (read-only), `runner` (`INITIAL_IDR`, `YearGap`), `tuning` (thresholds), `sim.rules` and `strategies.allocator`. `backtest.registry` imports `dev`, `sim.rules`, `strategies.a` (`STRATEGY_A`, for `REF-A-V0`), `strategies.allocator`, `strategies.base` and every family module. None of them imports `bars`, `db`, `http` or `config`.
- `research` (impure) imports `config`, `dates`, `fx`, `membership`, `yahoo` (the dividends-aware download), `prices`, `backtest.benchmark`, `backtest.io` (`histories_from_frame`, `merge_intervals`) and `backtest.market`; it never imports `db`. `commands.research_store` imports `research`, `backtest.io` (the vendored SPY dividends for `--verify`, and `read_facts` for `--with-fundamentals`) and `seer_engine.fundamentals` (`Fact`, a type only); it still names neither `seer_engine.db` nor `psycopg`. `research` also imports `seer_engine.fundamentals` (`FACT_COLUMNS`, `Fact`, `FundamentalPanel`). `backtest.io` imports `seer_engine.fundamentals` and `seer_engine.db` (for `read_facts`). `backtest.io` also imports `dev_report` (for `dev_report_files` and `write_dev_report`). `commands.backtest_dev` imports `config`, `research`, `backtest.dev`, `dev_report`, `registry`, `backtest.io`, `benchmark`, `market`, `metrics`, `runner` and `sim`, and `subprocess` for the `git status` registry check.
- `strategies.c` imports `dates`, `sim` (`Pick`), `strategies.a` (`STRATEGY_A`, `STRATEGY_A_PARAMS`, `AParams`) and `strategies.base`; never `finnhub`, `llm`, `db` or `universe`. `finnhub` imports `config`, `http` (`redact`), `requests` and `strategies.c` (`Headline`). `commands.veto` imports `db`, `dates`, `demo`, `runs`, `finnhub`, `llm`, `commands.nightly` (`_parse_now`), `paper.roster`, `paper.store`, `sim.sizing` (`Pick`) and `strategies.c`.
- `commands.promote` (phase 5) imports `config`, `dates`, `db`, `lab.store`, `lab.method` (`discover`, inside the function), `paper.roster`, `paper.store`, `sim.rules` (`TradeRules`) and `psycopg.types.json.Jsonb`. It never imports `backtest.registry` (D1), and it is the only module that holds a Neon connection and a lab SQLite connection at the same time — sequentially, never in one transaction.
- `lab.prereg` (build-promotion-path phase 3) imports `config`, `lab.store` and `lab.method` (`METHOD_ID`, `config_digest`, `source_sha`), plus `sqlite3` from the standard library. `backtest.dev` (`FAILURE_LABELS`, `DEV_END`), `dates` (`next_session`), `lab.method.discover` and `commands.backtest_dev.registry_problem` — the same `git status` check `lab run` makes on a method file — are imported *inside* the functions that need them, so importing `lab.prereg` does not drag in `backtest`. `commands.lab`'s `promote` handler imports `lab.prereg` and `lab.runner.git_head` inside the function. It never touches Neon: the pre-registration is a lab-side artefact only.
- `lab.npolicy` (lab-luck-gate phase 1) imports numpy and `sqlite3` only at module scope; it imports `lab.store` (for `dev_trial_count`) *inside* `effective_n`, because `store` will import `npolicy` once the gate reads the policy and a module-scope import would close that cycle. It imports no `backtest` module, no `db`, no `config` and no `http`. Since phase 4, `lab.store.gate` is its one importer, and the import is likewise *inside* `gate` — so the cycle stays open at module scope in both directions, and `import lab.store` does not pull numpy in. `lab.store` keeps the same discipline for the rest of the derived verdict: `backtest.dev` and `backtest.tuning` are imported inside `owner_failures`, `dsr_at`, `sr_star`, `_blocking` and `reevaluate_method`, never at module scope.
- `delisting` (delisting-stress-roster-rules phase 1) imports numpy, `random.Random`, `backtest.dev` (`DEV_END`, `MEMBERSHIP_START`), `backtest.market` (`SPY`, `Market`, `Membership`) and `strategies.base` (`History`). It imports no `lab` module — `tests/test_delisting.py` asserts that, so the harness can never record a trial — and none of `bars`, `db`, `http` or `config`. `scripts/delisting_stress.py` is its only caller and is not part of the package.
- `paper.compare` (phase 3) imports nothing from the package at all — only the standard library — which is what keeps it portable to the leaderboard's TypeScript port. `commands.compare` imports `db`, `paper.compare` and `psycopg`, and reads one table.
- `paper.book` and `paper.replay` (phase 6) also import `MarketAware` and `prepare_for` from `strategies.allocator`; `paper.roster` imports `strategies.f_fundamental` (`FUNDAMENTAL`, `FundamentalParams`) and still never imports `lab.methods.*` — the lab must not become an input to a paper spec digest.
- `sean.ledger` (Sean phase 1) imports only the standard library (`bisect`, `decimal`, `zoneinfo`). `sean.marks` imports `yahoo` and psycopg. `sean.equity` imports `dates`, `sean.ledger` and psycopg. `commands.sean` (phase 4) imports `dates`, `db`, `sean.equity`, `sean.marks` and (phase 7) `sean.calibrate`. `sean.calibrate` imports `sim.costs` only, which is the one `sim` edge from `sean`. Nothing else in the engine imports `sean`, and `sean` imports no `paper`, `lab` or `strategies` module.
- `lab.real_costs` (Sean phase 7) imports `research`, `backtest.dev`, `backtest.metrics` (formatters), `lab.store`, `lab.method` and `sim.rules`. `lab.runner` imports `lab.real_costs.real_cost_problem` at module scope. `commands.lab`'s `costs` handler uses `real_costs`, `research`, `backtest.dev` and `lab.store`.
- `survivorship` (eodhd-survivorship-market phase 1) imports numpy, `research` (window constants and the store's line formats), `bars` (`to_volume`), `prices` (`to_decimal`) and `yahoo` (`DIVIDEND_QUANTUM`); never `lab`, `db` or `http`, and it makes no network call. `commands.survivorship_store` imports numpy, `config`, `dates`, `research`, `survivorship`, `dividend_announcements` and `commands.dividend_announcements` (`read_cache`); since phase 2 also `survivorship_alias`, `eodhd` and `membership`. `survivorship_alias` imports `dates`, `eodhd`, `research`, `survivorship` and `backtest.market` (`Membership`); never `lab` or `db`, and its one network call is through the client it is handed. `lab.remeasure` imports `refuse_survivorship_store` from `lab.runner`. Phase 3: `commands.market_series` imports `config`, `dates`, `research` and `backtest.window` (`Window`) only; no `http`, `db` or `lab`, and no network call. `research` imports `MarketSeries` and `EMPTY_SERIES` from `backtest.market`.
### Standard library
`argparse`, `importlib`/`pkgutil` (command discovery), `logging`, `contextlib`, `dataclasses`, `decimal`, `functools.lru_cache`, `re`, `time`.

## Reverse Dependencies

- Within `engine/`, the phase 2 to 4 modules consume the API above exactly as written in the plan's "Shared interface contract": `membership.py` and `commands/universe.py` (phase 2), `yahoo.py` and `commands/backfill.py` (phase 3), and `massive.py`, `splits.py` and `commands/nightly.py` (phase 4).
- Phase 5 will add `.github/workflows/{engine-ci,nightly,universe,backfill}.yml`, which invoke the CLI.
- P4 (nightly) will call `strategies.a.STRATEGY_A.picks(...)` with `STRATEGY_A_PARAMS` and write `STRATEGY_A_PARAMS.as_dict()` to `strategies.params`. P6 adds strategies B and C beside `a.py`, implementing the same `Strategy` protocol.
- P4 is blocked: the P3b gate failed, and `STRATEGY_A2_PARAMS` is `None`. Nothing may deploy Strategy A or A2. P6's Strategy B can reuse `backtest.walkforward` (handover §8 option (a)), if the owner chooses it.
- P4 stays blocked: the P6a gate failed, `STRATEGY_B_FROZEN` is `None`, and no model artifact is committed. Nothing may deploy Strategy A, A2 or B. B's one round has failed on this data. The owner chooses among the report's options (b), (c) and (d).
- P4 stays blocked through P7a: no registry candidate was eligible on the dev window, so P7b does not run, and nothing in `strategies/` or `backtest/registry.py` may be deployed. The owner decides next with the dev frontier.
- Nothing in `web/` imports the engine. The two share only the database schema and `schema_migrations`.
- P4 runs **paper-only** (owner option (b), 2026-10-04): `commands/paper.py` steps the frozen roster (`paper/roster.py`: `SPY`, `A` with `STRATEGY_A_PARAMS`, `F4-MOM12-N20-TREND` and `F1-SPY-SMA200-M` from `backtest/registry.py`, read-only) through the same `sim` and strategy/allocator code the backtests ran. Nothing is a real-money recommendation: SPY is the champion, and `strategies.params.backtest_gate.passed` is false for every entry.
- `web/lib/data.ts` reads `paper_state`, `book_positions`, `book_targets`, `book_trades`, `orders`, `equity_snapshots`, `news_vetoes` (P6, Positions' "Vetoed tonight"), `runs.paper_*` and `strategies.params`/`paper_start` (read-only; `params.backtest_gate.applicable`). The web never imports the engine; the schema in migrations 003 and 004 is the contract.
- `.github/workflows/nightly.yml` runs `migrate` → `nightly` → `veto` (P6, `continue-on-error`, 10 minutes) → `paper` → `paper_check` → `explain`; `.github/workflows/engine-ci.yml` runs `ruff check engine` (rules in `pyproject.toml`) before pytest.
- Sean (phase 4): `nightly.yml` ends with a `continue-on-error` "Sean marks" step (`sean marks`, 10 minutes). `.github/workflows/sean.yml` (`workflow_dispatch`, concurrency group `sean-writer`) runs `migrate` → `sean marks` and is dispatched by the site after an upload (`web/lib/sean/dispatch.ts`). The web shares only the schema in `015_sean.sql` with the engine and never imports it. The Overview page's graph is meant to read `sean_equity`. `web/lib/sean/ledger.ts` must stay in lockstep with `sean/ledger.py`.

## Concurrency

This package is not designed for concurrent use. It is single-threaded and uses one connection per command. Some state is held per process:
- `http._session` is a module-level `requests.Session`.
- `config._loaded` is a module-level flag.
- `dates._calendar`, `_year` and `_closes` are `lru_cache`d per process.

`sean marks` is the one command built to overlap with itself: the nightly step and a dispatched `sean.yml` run can run at the same time under different concurrency groups. `sean.equity.lock` takes `EXCLUSIVE` on `sean_marks` and `sean_equity` for the write transaction, which serializes the writers while readers keep the previous series.

The temp tables `_seer_bars_in` and `_seer_fx_in` are scoped to a session (`ON COMMIT DELETE ROWS`), so concurrent processes do not collide.

## Error Handling

- Custom exceptions: `config.ConfigError` (exit 2) and `http.HttpError(.status)`.
- Validation errors are `ValueError` or `TypeError` with a message naming the bad value or date.
- `runs` raises `LookupError` for an unknown or demo run id.
- `db.transaction` always re-raises after rolling back. Data helpers never commit.
- Secrets are redacted from every logged or raised URL and from `runs.error`.
- Nothing in the package panics or exits outside `cli.main`.

## Performance

- Bulk writes use COPY into a temp table and then one set-based `INSERT ... ON CONFLICT`. Writes that change nothing are skipped by the `IS DISTINCT FROM` guard, so re-runs cause no table bloat.
- The NYSE schedule is computed once per year and cached for the life of the process.
- Network calls are the expensive part. `get_json` waits 5 s, then 10 s, then 20 s between retries by default. `fx.fetch_range` makes one request per year.
- Simulator: `tests/test_sim_scenario.py::test_benchmark_2950_sessions_x_4_slots` runs 2,950 NYSE sessions (2015-01-02 onward) × 4 slots with `size_picks` + `step` every session on synthetic bars, using `Decimal` throughout. Measured: **0.20 s** on WSL2, Python 3.11 (bound in the test: 20 s). A 10-year backtest is therefore dominated by loading bars and computing signals, not by the simulator. Floats are not needed.
- Backtest (P3), measured on the 2026-10-02 data (1,817,429 bar rows, 663 symbols), WSL2, Python 3.11:
  - Load: about 25 s from Neon on a cache miss (one streamed `COPY`, timed from the run log), 0.7 s from the 90 MB pickle cache (including the fingerprint query).
  - `STRATEGY_A.prepare` over all symbols and dates: 2.8 s, once per command.
  - Grid: 81 in-sample runs in 37.7–39.0 s, about 0.5 s each.
  - Whole command: 1:09 cold, 0:46–0:53 with the cache; peak RSS 420 MB.
  - Bars live as float64 arrays; `Decimal` `Bar`s are built only for symbols with a live order and for SPY, so the simulator's share of the time stays small.
- Walk-forward (P3b), measured on the 2026-10-02 data (1,817,429 bar rows, 663 symbols), WSL2, Python 3.11:
  - Load: 0.6 s from the 90 MB pickle cache (about 37 s from Neon on a miss). `STRATEGY_A2.prepare` (Strategy A's columns plus SPY's regime column): 2.8 s, once per command.
  - Tuning: 324 combinations, sequential, in 236.9 s, about 0.7 s each. Each combination is **one** run over 2015-10-19 → 2025-12-31, sliced into the 9 folds' tuning windows with `metrics_through`. That is exact by the runner's prefix property, and about 9× less work than re-simulating every fold.
  - The five walk-forward runs (combined + 4 variants, 2018-01-02 → 2026-10-02) and their SPY curves: about 4 s.
  - Whole command: 4:13 for the first run, 4:14 for the re-run; peak RSS 430 MB.
- Strategy B walk-forward (P6a), measured on the 2026-10-02 data (1,817,429 bar rows, 663 symbols), WSL2, Python 3.11, scikit-learn 1.9.1:
  - Load: 0.7 s from the 90 MB pickle cache (about 18 s streaming from Neon on a miss). `STRATEGY_B.prepare` (the 18 raw window columns for every (symbol, date) with 200 bars, plus SPY's 3; 1,684,380 rows over 662 symbols): 4.6–4.8 s, once per command.
  - Candidate table and labels: 1,304,876 candidate rows ranked per date and labelled by the vectorized bracket labeler (1,304,243 with a valid bracket and a resolved label) in 12.4 s. It is one numpy pass per session offset over the still-open rows, not one `sim.step` per row.
  - Fits: 9 tree fits in 30.5 s and 9 ridge fits in 2.1 s, sequential, in fold order (up to 1,207,705 rows × 18 features in the last fold). The determinism probe (the last fold's tree refit at 1 thread and at the default) took 13.1 s.
  - The B and B-linear walk-forward runs (2018-01-02 → 2026-10-02): 17.1 s and 4.7 s; the SPY curves 0.02 s. The A2 information curve, recomputed through `backtest_wf`'s pipeline (D12): 242.6 s, about 73% of the command. Survivorship, passed nights and both calibrations: 3.5 s.
  - Whole command: 5:47 for the first run, 5:53 for the re-run (cache hits both); peak RSS 1,548 MB (the candidate table and the per-fold training matrices).
- Dev search (P7a), measured on the research store `5451195fd552` (2,490,793 bar rows, 539 symbols, through 2015-10-16; 130 MB on disk), WSL2, Python 3.11:
  - `research_store --verify` (sha256 of every file, the `DEV_END` scan and the three data checks, no network): 4.3 s.
  - `backtest_dev`: store load 2.11 s; 54 candidates, sequentially, from 0.07 s to 5.26 s each, each allocator's one-time feature preparation included in its first candidate (median 0.43 s; slowest `F9-SPY200D50-SWING50`); 45.2 s for all 54 including the survivorship table and SPY curves; rendering and writing the five files under 1 s (not logged separately; read from the log timestamps).
  - Whole command: 0:51 for the committed run, 0:49 for the identical re-run; peak RSS 847 MB. Well under D13's 60-minute threshold, so there is no process pool.
- Paper (P4), measured on Neon on 2026-10-04 from WSL2, Python 3.11, with the real data (bars through
  2026-10-02), as a rolled-back first night (`--dry-run -v paper`, four strategies started, 0 sessions stepped):
  - Windowed bars load: 247,310 bars since 2025-03-31 in 1.69 s (`store.load_market_window`, timed separately; inside the command the window, splits and dividends took about 5 s). The plan's probe: `COPY … WHERE date >= '2025-06-01'`
    219,575 rows in 2.34 s; `>= '2024-10-01'` 326,410 rows in 2.73 s. There is no pickle cache.
  - Whole command: 6.94 s wall, peak RSS 238 MB. That is well inside the nightly job's 45-minute timeout.
  - `paper_check` before any session: 1.38 s wall. Its cost grows with the paper window, one
    `run_rules` per strategy over `[paper_start, last_session]`.
  - Migration 003 left the database at 186 MB (186 MB before; bars are 177 MB of it). The paper tables
    grow by kilobytes per month.
- Veto (P6), measured on 2026-10-04 from WSL2 with a local smoke (10 liquid symbols, no database): Finnhub `company-news` median 0.29 s (its 1 s spacing already passed during the previous LLM call) and `calendar/earnings` median 1.26 s (including the spacing), LLM verdict (`glm-5.3`, thinking disabled) median 3.05 s (max 4.97 s), 45.1 s for all 10. A night is at most 10 candidates, about 1 minute; the workflow step's 10-minute limit bounds the worst case. Details: the runbook's "Strategy C: the news check".
- There is no benchmark coverage for the DB writers.

## Usage

### Setup and tests

```
python3.11 -m venv engine/.venv
engine/.venv/bin/pip install -e 'engine[dev]'
docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
engine/.venv/bin/pytest engine/tests
```

DB tests skip without `PG_TEST_URL`, and CI fails the build if they do — but only for *that*
reason. `engine-ci.yml`'s `Test engine` step greps `pytest -rs` output for the `pg_url` fixture's
own skip message (`PG_TEST_URL is not set; start Postgres with`), not for any `^SKIPPED` line as it
once did: the blanket grep could not tell a misconfigured service from a deliberate `skipif`, so it
reddened the build while printing the false message "PG_TEST_URL did not reach pytest". The step
first asserts that reason string still exists in `conftest.py` and fails loudly if it does not, so
rewording the fixture cannot silently disarm the guard — the two have to move together. A correctly
configured run is expected to skip a couple of tests (an opt-in live-store test and the like) and
that is not a failure. Each DB test gets
a throwaway schema `t_<hex>`. The fixtures are `pg` (migrated), `pg_empty`, `pg_schema`,
`pg_url` and `utc(y, m, d, h=0, mi=0)`. An autouse `_isolated_env` fixture points
`SEER_ENV_FILE` at a missing file and `DATABASE_URL_UNPOOLED` at a `.invalid` host, so no test
can reach `.env.local` or Neon.

### Settings
- `DATABASE_URL_UNPOOLED`: required by `db.connect()`.
- `SEER_ENV_FILE`: optional override for the dotenv path.

### Typical write command

```python
def run(args):
    with closing(db.connect()) as conn:
        demo.purge_demo_if_needed(conn, args.dry_run)
        rd = dates.run_dates()
        with db.transaction(conn, args.dry_run):
            run_id = runs.start_run(conn, rd)
            if run_id is None:
                return 0
            bars.upsert_bars(conn, fetched)
            runs.finish_run(conn, run_id)
    return 0
```

### Simulator: P3 backtest loop

History is already split-adjusted backwards, so the backtest never calls `apply_split`.

`backtest.runner.run_backtest` implements this loop; the sketch below is the shape.

```python
from decimal import Decimal
from seer_engine import dates
from seer_engine.sim import (
    Snapshot, close_unpriced, initial_cash_usd, new_portfolio, size_picks, step,
)

pf = new_portfolio(initial_cash_usd(Decimal("20000000"), usd_idr_on(start)))
events, snapshots = [], []
for session in dates.sessions(start, end):
    picks = strategy.picks(data_date=dates.prev_session(session))  # ranked Picks, made after that close
    pf = size_picks(pf, picks, session).portfolio
    result = step(pf, session, bars_on(session, pf.held_symbols()))  # {symbol: Bar}; missing = no bar
    pf = result.portfolio
    events += result.events
    snapshots.append(result.snapshot)
    gone = delisted_after(session, pf.open_orders())  # P3 knows from data when a symbol's bars end
    if gone:
        pf, forced = close_unpriced(pf, gone)
        events += forced
        snapshots[-1] = Snapshot(session, pf.cash, pf.equity)
```

### Paper: one night (P4)

The night as `commands/paper.py` runs it, after `nightly` has succeeded for `rd.session_date`.
Every arrow below is a call into code the backtests also run.

1. `rd = dates.run_dates(now)`; refuse (exit 1, nothing written) unless the real `runs` row for `rd.session_date` is `success`.
2. `entries = roster.from_rows(store.read_roster_rows(conn))`: the roster is the database's, not the compiled `ROSTER`, and an unresolvable row stops the night here by name. Then `plan_night(entries, rows, states, rd)` reads every strategy's `store.read_paper_state`, checks each **active** entry's frozen digest (`store.check_digest`) and returns a `NightPlan(start, step, retired)` — the entries that start tonight, the `(entry, state)` pairs that step, and a `Retired(entry, paper_end, stamp)` per `status = 'retired'` row. `NightPlan.empty()` (nothing starts, nothing steps, no retirement left to stamp): exit 0.
3. `runs.start_paper` (its own short transaction). Then, in one transaction (`_night`): first every retirement whose `paper_end` is still NULL is stamped (`store.set_paper_end`), the only write a retired strategy ever gets; then, only when something actually starts or steps, `_trade` loads the windowed market (`store.load_market_window(conn, since)` with `since = store.market_window_since(earliest)`, 550 calendar days before the earliest session to step), the applied splits per session (`store.applied_splits_on`) and the dividends (`store.dividends_between`). Each session S is computed on `night_view(market, S, later_factors(...))`: the market as it stood on S's night, later bars and FX hidden, splits executed after S undone on bars and dividends.
4. First night only (`_start`): `store.freeze_spec` writes each frozen spec (`roster.strategy_params(e)`) and `paper_start = rd.session_date`; `store.init_paper_state` writes `paper_state` (initial cash `initial_cash_usd(INITIAL_IDR, the latest fx_rates rate ≤ rd.data_date)`) and the day-0 snapshot at `rd.data_date`; then the decision for `paper_start`.
5. Per strategy, once before any session steps: `store.accrue_contributions(conn, e.id, OWNER_MONTHLY.dates_in(paper_start, sessions[-1]), OWNER_MONTHLY.amount_idr, through=sessions[-1], usd_idr_on=…)` records every deposit that has landed, each frozen at the USD/IDR of its own landing session.
6. For every session S after `paper_state.last_session` through `rd.data_date`, per strategy — each first taking `credited = store.apply_contributions(conn, e.id, S)`, the deposits landing on S:
   - A, C-GT: `paper.bracket.settle_bracket(pf, S, bars, splits, last_bar_date, rules=e.rules)`, which is `apply_split` per applied split, then `sim.step`, then `close_unpriced`, with the snapshot replaced; `credited` is added to **both** `pf.cash` and `pf.equity` first, because sizing reads the last snapshot's equity; `store.save_bracket_night`; then `decide_bracket(pf, e.obj, e.params, history, members, S, rules=e.rules)` → `store.insert_pending_orders`, `store.write_pending`;
   - C: exactly as A, with `e.obj.with_allowed(store.allowed_between(conn, "C", first, last))` as the strategy, so its picks are A's first 10 minus every symbol without a stored `allow`;
   - the books: `credited` goes in through `paper.book.deposit_book(book, credited)` (cash and equity together), then `paper.book.settle_book(book, S, bars, targets, idle_added, rules, dividends, splits, last_bar_date)`, which is `sim.apply_book_split` per applied split, then `sim.step_book`, then `close_book_unpriced`; `store.save_book_night(..., executed_targets=)`; then `decide_book(view, e.obj, e.params, rules, S, held)` → `store.save_book_decision` (targets, or `None` when the next session is not a month's first);
   - SPY-GT: `paper.benchmark.step_benchmark(state, S, bar, dividend, split=<applied SPY split on S or None>, deposit=credited)` — the state loaded at `roster.benchmark_cost_model(e.id)`, and the deposit **spent at that close**, not banked, so the yardstick is the dollar-cost-averaged SPY the books are measured against; `store.save_benchmark_night`, `store.write_pending`.
7. `runs.finish_paper` sets `runs.paper_status = success` inside the same transaction, so a failure rolls back everything; `runs.fail_paper` then records `paper_status = failed` and the redacted error in its own transaction (exit 1).

Run it:

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine --dry-run -v paper   # rolled back
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine -v paper_check
```

The real night runs only in `nightly.yml` (Veto → Paper → Paper check → Explain).

### Paper: replay check (P4)

`paper_check` re-runs `backtest.book_runner.run_rules` (A, F4, F1 and, since phase 6, FND — the
latter through `run_rules(..., prepared=…)`, the branch `decide_book` took) and the `buy_and_hold` rules
(SPY) over `[paper_start, last_session]` on the same windowed market, with `paper_state.usd_idr`, and
compares them with the stored state through `paper.replay` (pure: `expected_bracket`,
`expected_book`, `expected_benchmark`, `compare`, `judge`): every snapshot, order, fill, closed trade,
stored decision and open position. A bracket entry is replayed under its own `rules` and all three
engines are replayed on the entry's stored, dated, already-converted deposits (the `applied`
`paper_contributions` rows), never on the schedule that produced them. `--require-sessions N` also
demands ≥ N stepped sessions per strategy. That is the v0.1.0 release check.

### Why this pick: evidence → explain (why-this-pick-pipeline)

How a pick gets its "Why this pick" text, end to end:

1. **Evidence (pure, phase 1).** `strategies/evidence.py` has one function per `paper.roster.RESOLVER` name (`STRATEGY_A`, `STRATEGY_C`, `FACTOR`, `TIMING`, `FUNDAMENTAL`; the benchmark has none). Each one, `(market, params, data_date, symbols) -> {symbol: facts}`, recomputes the numbers the formula ranked on, such as a 2-day strength score, the distance from the 200-day average, 12-month momentum and its rank among eligible stocks, or filed fundamentals compared with the eligible set. It returns them as 2–6 plain sentences with the numbers already formatted. It reads nothing dated after `data_date`, and it never touches a params class, so no roster digest moves.
2. **Storage (Paper, phase 2).** At decision time `commands/paper.py` calls the evidence function on the decision's own market view for the decided symbols. Any exception gives NULL for that night. The facts go into `orders.evidence`, `book_targets.evidence` and `book_previews.evidence` (migration 009). The decisions themselves are byte-for-byte unchanged.
3. **Explanation (Explain, phase 3).** `explain` sends the method's plain name, the symbol and the stored facts, with thinking disabled. It keeps a reply only if `vet` passes: 2 complete sentences at most, ≤ 320 characters, every number taken from the facts, no advice or prediction words, and no copy of another note for the same strategy that night. Otherwise the text stays NULL.
4. **Display (web, phase 5).** "Why this pick" shows the note. When the note is NULL but there is evidence, it shows the facts as a short list. It says "unavailable" only when both are missing. "Would pick now" rows show their facts, with no LLM. C keeps its "Why it passed the news check" line.
5. **Promotion (phase 4).** `promote` refuses a lab method whose allocator has no `EVIDENCE` entry.

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine --dry-run -v explain   # real LLM calls, rolled back
```

### Strategy C: the news check (P6)

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine --dry-run -v veto   # real calls, rolled back
```

`veto` needs `FINNHUB_API_KEY` and `LLM_*` (with `LLM_MODEL=glm-5.3`); without them every verdict is
`failed`. Only the nightly job runs it for real. Then `paper` decides C from the stored verdicts and
`paper_check` replays it from the same rows.

### Backtest: run and read the report

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine backtest
```

Then read `docs/backtests/<data end>-strategy-a.md`. If `STRATEGY_A_PARAMS` differs from the new
report's `selected-params:` line, `test_strategy_a_frozen.py` fails until the constant is updated
(with its comment) or the report is not committed.

### Backtest: walk-forward (P3b)

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine backtest_wf
```

Then read `docs/backtests/<data end>-strategy-a2-walkforward.md`. Its `p3b-gate:`,
`last-fold-params:` and `frozen-params:` lines are what `test_strategy_a2_frozen.py` reads:

- On a passing report, `STRATEGY_A2_PARAMS` must equal `last-fold-params:`, and the comment above
  it must name the report.
- On a failing report, it must be `None`.

A newer report with a different outcome or selection fails the test until the constant follows it.
Committing a newer report is a re-measurement on new data, not a new rework.

### Backtest: Strategy B walk-forward (P6a)

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine backtest_b
```

Then read `docs/backtests/<data end>-strategy-b-walkforward.md`. Its `p6a-gate:`, `gated-model:`,
`last-fold-model:` and `frozen-model:` lines are what `test_strategy_b_frozen.py` reads:

- On a passing report, `backtest_b` also writes `engine/data/models/<data end>-strategy-b.pkl` and
  logs its sha256. `STRATEGY_B_FROZEN` must name the report, that artifact, its sha256 and the last
  fold's `train_end`. The artifact must load (`b_model.loads`) to the `last-fold-model:` digest, and
  the comment above the constant must name the report. Re-run after freezing, so the report records
  `frozen-model:`.
- On a failing report, the constant must be `None`, and no `*-strategy-b.pkl` may be committed.

A newer report with a different outcome or model fails the test until the constant and the artifact
follow it. Committing a newer report is a re-measurement on new data, not a new round.

### Research store and the dev search (P7a)

```
cd <repo or worktree root>
engine/.venv/bin/python -m seer_engine research_store            # build engine/.research (network; 30-60 min)
engine/.venv/bin/python -m seer_engine research_store --verify   # no network: sha256s, window guard, data checks, fingerprint
engine/.venv/bin/python -m seer_engine backtest_dev              # every REGISTRY candidate, dev window only (~1 min)
```

The test-window store is a separate build, done on the first promotion and never before (design S3):

```
engine/.venv/bin/python -m seer_engine research_store --test-window                          # engine/.research-test, through the latest session
engine/.venv/bin/python -m seer_engine research_store --test-window --window-end 2026-10-02  # resume an interrupted build to the same end
engine/.venv/bin/python -m seer_engine research_store --test-window --verify                 # its own window, its own fingerprint
```

Neither store can be used in the other's place: `--test-window` against `engine/.research` (or a
dev invocation against `engine/.research-test`) exits 2 — as does any build whose target already
holds a store declaring the other window, wherever on the machine that store lives — and
`load_store` refuses the mismatch before it reads a data file.

Spending the one look on that store is `lab test` (build-promotion-path phase 4), after the method
has been pre-registered by `lab promote` and that file committed **and pushed**:

```
engine/.venv/bin/python -m seer_engine lab test M0007-RESID --dry-run  # loads nothing, runs nothing, spends nothing
engine/.venv/bin/python -m seer_engine lab test M0007-RESID            # the one counted look; test-passed or test-failed, both final
```

Neither command needs `SEER_ENV_FILE`: neither reads Neon. Then read
`docs/backtests/<run date>-p7a-dev-exploration.md` and `docs/plans/<run date>-p7b-preregistration.md`.
The report's store fingerprint must equal `research_store --verify`'s, and its registry digest must
equal `sha256sum engine/src/seer_engine/backtest/registry.py` at the committed registry.

To add a candidate (D6): append it to `REGISTRY`, pin its `(id, digest)` in `tests/test_registry.py`,
and commit both **before** running it. A smoke run of one candidate is `backtest_dev --only <ID>`,
which writes nothing. A committed report always comes from a full run over a clean registry.

### Sean: mark the owner's holdings (Sean phase 4)

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine --dry-run -v sean marks   # rolled back
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine -v sean marks --now 2026-10-07T23:00:00Z
```

In production it runs through `sean.yml` (dispatched by the site after an upload, or by hand with
`dry_run`) and as the last nightly step. Tests: `tests/test_sean_ledger.py` (the shared fixture),
`tests/test_sean_marks.py`, and `tests/test_sean_command.py` (the DB tests need `PG_TEST_URL`).

After a batch of new order screenshots, check the fee schedule (exit 1 means refit `sim/costs.py`):

```
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine sean calibrate
```

To see what Gotrade's real fees do to an older (flat-cost) lab method, run this report-only
command. It writes a journal note, never a trial:

```
engine/.venv/bin/python -m seer_engine lab costs M0022
```

### Gotchas
- Do not use `with psycopg.connect(...) as conn`, because it commits on exit and defeats `--dry-run`. Use `contextlib.closing` instead.
- Every write must be inside `db.transaction(conn, dry_run)`. The helpers never commit, so a write outside it is lost or left open.
- `demo.purge_demo_if_needed` must run before the first write. Any demo `runs` row means `bars` and `fx_rates` will be TRUNCATEd.
- Never build a local-midnight datetime from a date. Pass `date` objects, and give `last_completed_session`/`run_dates` an aware UTC datetime.
- Convert symbols to Yahoo's dash form (`BRK-B`) only inside the Yahoo adapter (phase 3). Tables always store `BRK.B`.
- `universe.end_date` is exclusive.
- Under `--dry-run`, `migrate` reports the files it would apply, but leaves no `schema_migrations` table behind.
- **The dev window is law.** Every dev entry point raises `backtest.dev.DevWindowError` for a session after 2015-10-16, and `research.load_store` rejects a store holding a row after the window it was asked for — `DEV_WINDOW` unless the caller says otherwise, and `lab run` and `backtest_dev` never say otherwise. Never add a flag, a default or a store that gets past either guard. P7b runs the pre-registered finalists on the test window under its own handover.
- **A dev store and a test store are never interchangeable** (build-promotion-path phase 2; the build guard is content-based since research-store-clobber-guard). They live in different directories (`engine/.research` vs `engine/.research-test`) and a store declares which it is in its manifest, so `load_store` refuses the wrong one *before* reading any data file, and `research_store` refuses to build or verify one window against the other's directory even when `--store` names it explicitly — the **build** check reads the target's own `manifest.json` (`research.declared_window`), not the `--store` path, so it refuses a wrong-window store in **any** checkout or worktree and not merely this one, and falls through only when the directory holds no readable store at all. Do not "fix" a mismatch by pointing `--store` or `SEER_RESEARCH_STORE` somewhere else: the test store holds the same history **and** every session after `DEV_END`, so running the dev pipeline on it would spend unseen data silently.
- **The dev store's manifest is nine keys, and a dev build must never write a tenth.** `window_name` / `window_start` / `window_end` are `OPTIONAL_MANIFEST_KEYS` and **absent means the dev window** — never a `window_name: "dev"`. `engine/.research` was sealed with exactly `MANIFEST_KEYS`; requiring a window key, or writing one on a dev build, would reject or re-seal the store whose fingerprint `/sync-research-store` keys on and every recorded lab trial was measured against.
- **The test store starts in 1993, not in 2015.** `TEST_WINDOW_START` (2015-10-19) is the first session the test window *trades*; `STORE_START` is where its data begins, the same as the dev store's. A candidate first traded on 2015-10-19 still needs its `lookback` bars before that date, and the lab gets exactly one append-only look per configuration, so a test store opening at its own window start would make that one look permanently and unrecoverably wrong.
- **Build the test store on the first promotion, never before** (design S3), and pin `--window-end` when resuming an interrupted build. Without the pin the window silently moves to whatever the latest completed session is that day, which changes what a recorded test trial meant.
- **The registry is append-only.** `tests/test_registry.py` pins every `(id, digest)`. A new candidate is appended and pinned in its own commit, before its dev run (D6). Editing an entry after its result exists is not allowed, even to fix a "typo": append a new id instead, and it counts as a trial.
- `backtest_dev` refuses a full run (exit 2) while `backtest/registry.py` has uncommitted changes. `--only` skips that check and writes nothing; its numbers are a smoke test, never a result.
- **Paper state stays in the units it was sized in.** Never rebuild a mark or a price of a live paper order or position from `bars`: `nightly` rewrites history backwards on a split, and `apply_split` / `apply_book_split` would then rescale it twice. Marks are stored (`orders.mark`, `book_positions.mark`).
- **A roster entry is frozen.** `paper` fails the night (`store.SpecMismatch`, rolled back, `runs.paper_status = failed`) when a started strategy's stored spec digest differs from `paper/roster.py`'s. Change a strategy by adding a new id (its own `paper_start`), never by editing a started one or deleting its rows.
- **`RESOLVER` keys are forever, and an unknown one stops the build.** A stored spec names its `object_name`, so renaming or removing a key a started strategy still names would move a live digest. Append only. And `roster.from_row` raises `UnknownObject` rather than skipping a row it cannot resolve: a dropped portfolio is a hole in a track record that nothing later can fill, so the whole build fails loudly instead.
- **`promote` never appends to `backtest/registry.py`** (D1). The registry is the P7a dev-run candidate set, fixed before that run and digest-pinned; a promoted method reaches the roster through `paper.roster.RESOLVER` instead, so the lab's multiple-testing count stays honest. Add the `Binding` to `RESOLVER`, never a `REGISTRY` entry.
- **A promotion leaves `paper_start` NULL on purpose.** `promote` writes the row; the next paper night freezes the spec and starts the clock. Never back-date a promoted entry's `paper_start`, and never re-point a started id at another algorithm — `promote` raises `AlreadyStarted` for exactly that. Promote under a new id and `--retire` the old one in the same command, so the swap is one transaction.
- **The roster write and the lab note cannot be one transaction** (Neon and SQLite). The roster commits first; if the lab note is then lost, re-run the identical `promote` command — both halves are idempotent. Never reorder them: the lab is append-only, so a note for a promotion that did not happen cannot be withdrawn.
- **A pre-registration is written once and never rewritten** (design §3). `lab promote` leaves an existing `docs/lab/prereg/MNNNN.md` byte-for-byte alone, date line included, and raises rather than re-pointing it at a better variant found later; if the first choice is genuinely wrong, that is a new method with its own dev trials. And the file must be committed **and pushed before** `lab test`: `prereg.require_committed` refuses on a file git does not track or that has staged or unstaged changes, which is the whole point of putting the record in git.
- **The gate named in a pre-registration is the dev gate, not the test gate.** `prereg.gate_text` states what the variant passed to become `dev-eligible` (the five P7a D8 conditions plus `DSR >= store.DSR_MIN`, deflated by the N that `store.DSR_POLICY` resolves to — both pinned into the file, because both are settings the owner can move; design §7). The one test-window look is judged by the five D8 conditions alone; DSR is recorded on the test trial and is not a condition, because a pre-registered look has no selection among results to deflate and a look is not a search.
- `paper` runs only after a successful bars run for the same session, and only in the `seer-db-writer` concurrency group. Never run a real (non-`--dry-run`) `paper` locally against Neon while the scheduled job may run, and never before the code is on `main` (D11: no back-dated paper days).
- `paper_check` reports a strategy `split-affected` (not failed) once an applied split touched a symbol it held or had pending: whole-share rounding before and after a split cannot match a replay over adjusted bars.
- `explain` must never decide anything: it writes text only, and a failure leaves NULL. It reads only stored evidence. Never add order mechanics, rule text or anything outside the facts to its prompt, and never loosen `vet` to let a reply through: a NULL note shows the facts on the site, while a wrong note shows advice the facts do not support.
- **C's verdicts are decided once.** `paper_check` replays C from `news_vetoes` and never re-asks the LLM. Never edit, delete or re-run verdicts for a session Paper already decided: the replay would no longer match what Paper did. `veto` refuses on its own once the session is checked or decided.
- **C's model is part of its spec.** `LLM_MODEL` must be `glm-5.3`; another value makes every C verdict `failed`. Editing `strategies.c.FROZEN_MODEL`, the prompt or any `CParams` field changes C's digest and fails the whole night with `SpecMismatch`. A different model or prompt is a new roster id.
- **No look-ahead in news.** `select_headlines` keeps only items published before the `veto` run started (`decided_at`); the earnings window is the schedule as known then.
- **Rebuild a `Market` with `dataclasses.replace`, never `Market(history=..., membership=..., fx=...)`.** Every windowing site that re-listed the fields by hand (`paper.replay.expected_bracket`, `commands.paper.night_view`, `backtest.dev`'s FX-window copy) now uses `replace`, so a new field such as `fundamentals` is carried over instead of being silently dropped back to the empty panel. Use `market.with_fundamentals(panel)` to attach one.
- **`prepare_market` must not be added to the `Allocator` protocol.** `Allocator` is `runtime_checkable` and several production sites test `isinstance(x, Allocator)`; adding a member — even one with a default body — makes every structural implementer fail the check. Implement `strategies.allocator.MarketAware` alongside it and let `prepare_for(obj, market)` dispatch.
- **Fundamentals are optional everywhere they are read.** A database with no `fundamental_facts` / `ticker_cik` (or no rows) loads to `EMPTY_FUNDAMENTALS`, and a research store built before the panel existed loads with a bit-identical fingerprint. Never make either an error: the backtest must stay runnable on a database that has not applied `005_fundamentals.sql`.
- **The survivorship-check store is never a trial source.** `engine/.research-sv` loads exactly like a dev store (same window, same readers); only its manifest's `purpose` key tells them apart, and `lab run` / `lab test` / `lab remeasure` refuse it on that key. Never strip the key, never point a recording command at it, and never commit it (EODHD rows are licensed to the owner personally).

## Notes

Documentation created on 2026-10-03 for P1-ENG-VP1R (phase 1). Phases 2 to 4 (P1-ENG-853Z,
P1-ENG-L73U, P1-ENG-GF8Y) will add the `universe`, `backfill` and `nightly` commands, and this
document should gain their sections when they land. The full design, invariants and
reconciliation log are in `ENGINE_DATA_PIPELINE_PLAN.md`.

The P3 sections (`strategies`, `backtest`, the `backtest` command and the committed report) were
added on 2026-10-03; their design, invariants and decisions are in `STRATEGY_A_BACKTEST_PLAN.md`
and `docs/handover/2026-10-03-strategy-a-backtest.md`.

The P3b sections (`strategies.a2`, the walk-forward modules, the `backtest_wf` command and the
committed walk-forward report) were added on 2026-10-03. Their design, invariants and decisions are
in `STRATEGY_A_REWORK_PLAN.md` and `docs/handover/2026-10-03-strategy-a-rework.md`.

The P6a sections (`strategies.b_model`, `strategies.b`, the labeler, the B walk-forward and report
modules, the `backtest_b` command and the committed P6a report) were added on 2026-10-03. Their
design, invariants and decisions are in `STRATEGY_B_RANKER_PLAN.md` and
`docs/handover/2026-10-03-strategy-b-ranker.md`.

The P7a sections (`sim.rules`, `sim.book`, the allocators and families F1–F11, the book runner, the
research store, the dev runner, report and registry, the `research_store` and `backtest_dev`
commands, and the committed dev report and P7b pre-registration) were added on 2026-10-04. Their
design, invariants and decisions are in `TRADE_RULES_DEV_SEARCH_PLAN.md` and
`docs/handover/2026-10-03-trade-rules-revision.md`.

The P4 sections (`paper/*`, the `paper`, `paper_check` and `explain` commands, `dividends`, `llm`,
the book split rule, migration 003, the P4 additions to `massive`, `splits`, `nightly`, `universe`,
`runs`, `demo` and `backtest.io`, and the real nightly flow under Usage) were added on 2026-10-04.
P4 runs paper-only by the owner's option (b) of 2026-10-04: no real-money recommendations, design §1
unchanged. Design, invariants and decisions: `PAPER_TRADING_SHIP_PLAN.md` and
`docs/handover/2026-10-04-paper-trading-ship.md`; operations: `docs/runbooks/paper-trading.md`.

The P6 Strategy C sections (`strategies.c`, `finnhub`, the `llm` call options, roster entry `C`,
the `news_vetoes` store, migration 004, the `veto` command, and C in `paper`, `paper_check` and the
nightly flow) were added on 2026-10-04. C runs on paper only: no backtest gate applies to an LLM
strategy (design §1 item 5), and real money for C would need an explicit owner decision. Design,
invariants and decisions: `STRATEGY_C_NEWS_VETO_PLAN.md` and
`docs/handover/2026-10-04-strategy-c-news-veto.md`; operations: `docs/runbooks/paper-trading.md`.

The roster-as-data sections (migration 006, `paper.roster`'s `RESOLVER`, `Binding`, `Row` /
`RosterRow`, `from_row` / `from_rows`, `SEED_ROWS`, `active` and the `RosterError` family, and
`paper.store.read_roster_rows` with the widened `StrategyRow`) were added on 2026-10-05 as phase 1
of `ROSTER_PROMOTION_PIPELINE_PLAN.md`. This phase is pure plumbing: `ROSTER` is now
`from_rows(SEED_ROWS)` instead of a hand-written tuple, the five spec digests are byte-identical
and still pinned in `tests/test_paper_roster.py`, and `paper`, `paper_check` and `veto` continued to
read the compiled `ROSTER`.

Phase 2 landed on 2026-10-05 (P1-ENG-J5XD): `paper` and `paper_check` now build their entries from
the stored rows, `commands/paper.py` gains `Retired` and a third `NightPlan` leg (a retired entry is
a deliberate skip, never an error, and never the code path an unresolvable row takes), `_night`
splits into `_night` (which settles retirements, and loads no market window when nothing trades) and
`_trade` (never called with nothing to do), and `paper/store.py` gains `retire` and `set_paper_end`
as the only writers of the lifecycle columns.

Phase 5 landed on 2026-10-05 (P1-ENG-Z8MR): the `promote` command (`commands/promote.py`) and
`lab.store.record_promotion` / `PROMOTION_MARKER`. It is the lab → roster bridge and the only
writer that creates a roster entry: one `strategies` INSERT (`status='active'`, `promoted_from`,
`registry_id` NULL, the full contract-C2 `params`, no `paper_start`), proved by a
`roster.from_row` round trip inside the same transaction, optionally atomic with phase 2's
`store.retire`; and one append-only, idempotent lab note that moves the method's status only along
the existing `('test-passed','paper')` edge. `backtest/registry.py` is untouched by design
(Decisions D1), and the roster's admission rule is deliberately not the lab's gate (Decisions D5),
which is what `--lab-status-stays` makes explicit.

Phase 3 landed on 2026-10-05: `paper/compare.py` (pure) and the read-only `compare` command. It
replaced "rank by whatever each strategy's own span happened to return" with a comparison over the
window every ranked strategy shares, stated rather than implied, with inception-to-date kept
separate and never ranked (invariant 6). Its readme sections were written up with phase 6, because
phase 3 landed while its peers were committing concurrently.

Phase 6 landed on 2026-10-05 (P1-ENG-H3WF), the last of the set: `FND · Fundamentals` joined the
roster as its sixth entry (migration 007, `roster.FND_ID` / `FUNDAMENTAL_PARAMS` / the `FUNDAMENTAL`
`RESOLVER` binding, `tests/test_paper_fnd.py`), put on the live board by phase 5's `promote` — the
first promotion through the new lab → roster path rather than around it. It carries a `gate_note`
that says it **failed** its M0005 dev-window gate, which is the honest statement: a backtest gate has
never been this roster's admission criterion (Decisions D5) and it binds the real-money decision, not
paper membership. Because FND is the roster's first `MarketAware` object, `paper/book.py:decide_book`
and `paper/replay.py:expected_book` now dispatch such an allocator through `prepare_for` +
`targets_prepared`, so it actually reads `market.fundamentals`; before this a `MarketAware` allocator
on the roster would have held cash forever while every log line said it had decided. The branch is
keyed on the protocol alone, so for every allocator that is not `MarketAware` the expression is
byte-identical to before: the five pre-existing spec digests are unchanged, the five strategies with
a paper clock replay bit for bit, and `MAX_LOOKBACK_BARS` is still 253.

Phase 3 of `BUILD_PROMOTION_PATH_PLAN.md` landed on 2026-10-06 (P1-ENG-AZ81): `lab/prereg.py`, the
committed pre-registration format it owns (`docs/lab/prereg/MNNNN.md`, with
`docs/lab/prereg/README.md` stating that format for a human reader), `lab.store.best_dev_eligible`
and the `lab promote` subcommand. It supplies the half of the one-look rule a database cannot
enforce: SQLite counts the looks (`UNIQUE(config_digest, window)` and the append-only triggers), and
the committed file names which configuration each look is spent on, before any test number exists.
All three source edits are pure additions (90 insertions, 0 deletions) and `lab run` is
behaviourally unchanged. Tests: `tests/test_lab_prereg.py` (25) and one case in
`tests/test_lab_store.py`.

Phase 4 of `BUILD_PROMOTION_PATH_PLAN.md` landed on 2026-10-06 (P1-ENG-YJDW), the last of the set:
the `lab test` subcommand and the test-window half of `lab/runner.py` (`Tested`,
`resolve_candidate`, `preflight_test`, `test_trial_row`, `run_test`). `runner.py` is appended to and
nothing above its `lab run` half changed, so `lab run` is behaviourally unchanged. It closes the
path the first three phases built: phase 2's second store supplies the data, phase 3's committed
pre-registration says which configuration the look is spent on, and this phase spends it — one
`window = 'test'` trial row that does not move the lab's N, a verdict of `test-passed` or
`test-failed` (both final), and on a pass the exact `promote` line that hands the method to phase
5's existing roster path. The one-look rule is enforced in two places on purpose: readably in
`preflight_test`, and in the database by `UNIQUE(config_digest, window)` — the second is the one
that holds against a parallel session, which is why `run_test` re-runs the preflight inside its
write lock. The mechanism is built and **nothing has been spent**: `test-window looks used` reads 0
against the real lab. Tests: `tests/test_lab_test_window.py`, with the fixtures in
`tests/labkit.py`.

Phase 6 of `LAB_LUCK_GATE_PLAN.md` landed on 2026-10-07 (P1-ENG-CA69): every paper roster entry
that came from a recorded lab candidate now states its lab provenance in code. `paper/roster.py`
gains `Basis` / `BASES`, the frozen `LabProvenance` (method, variant, the lab status at admission,
the basis, and the reason — with an unexplained `owner-override` refused in `__post_init__`), the
`LAB_PROVENANCE` table keyed by roster id, and a `lab_provenance` field on `RosterEntry` that
`from_row` fills from that table; `lab/store.py` gains `PROMOTION_BASES` and `promotion_basis`,
and `record_promotion` takes `basis=` / `reason=`, writes `Lab status at admission` and `Basis`
into the method's analysis, and refuses an unexplained override; `commands/promote.py` gains
`--lab-override-reason`, requires it whenever the method is not at `test-passed`, shows the
provenance in `render_plan`, and prints the `LAB_PROVENANCE` entry to add in the same commit. It
closed a *documentation* gap, not a policy one: paper membership has never required a gate pass
(Decisions D3), the method lab's design §3 and §6 read the other way, and the owner's rule — a lab
test pass is a sufficient basis for a paper entry, never a necessary one — now sits in the roster's
module docstring instead of being inferred from the fact that `FND`, `RM-FR` and `RMW-FR` trade
while their methods read `rejected`. The field sits outside the spec exactly where `gate_note`
does, so **no `spec_digest` moved and no entry was retired**. `tests/test_paper_roster.py` checks
every provenance line against the committed `lab/lab.sqlite` (`COMMITTED_DB`, not `SEER_LAB_DB`,
for the same reason `test_lab_methods.py` reads it that way): the method exists, the variant is a
recorded **dev** trial of it, an `owner-override` names a trial the dev gate did not pass
(`eligible = 0` — otherwise nothing was overridden and the basis is wrong), a `test-passed` names
a passed test-window trial, and the method's *live* status is the admission status or forward of
it along `TRANSITIONS`, which is all a forward-only machine can still prove about a frozen fact.
A Postgres case also checks `LAB_PROVENANCE` agrees with the `promoted_from` column on the three
rows `promote` wrote (`FND`, `RM-FR`, `RMW-FR`). Further cases in `tests/test_lab_store.py` and
`tests/test_promote_command.py`.

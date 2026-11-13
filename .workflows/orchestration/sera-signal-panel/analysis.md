# Code Analysis: Sera signal panel (stage one of the method lab)

**Type:** Feature Implementation
**Date:** 2026-11-13 20:05 WIB
**Session ID:** 20261113-200537-K7P2
**Plan:** `.workflows/plan/SERA_SIGNAL_PANEL_PLAN.md` (7 phases)
**Worktree:** `/home/miftah/.worktrees/seer/sera-signal-panel`, branch `feature/sera-signal-panel` (base `origin/main` @ `b0652d2`)

---

## User Input

### Original User Request

> let's go. /analyze it so we can ship a robust solution

The "it" is the proposal the owner approved in the same conversation, passed to `/analyze` as:

Build a signal panel as stage one of Sera's exploration (the Seer method lab), so a stock-picking idea is screened on a stock-by-month panel before it ever becomes a full book backtest.

Problem (measured this session from lab/lab.sqlite, read-only): 664 methods, 422 run in 2,265 dev backtests, 184 dev-eligible, 0 promotable (hard gate refuses 179), 6 of 6 test looks failed on "beats SPY TR". 350 of the 464 methods with a verdict are stock-signal families. 32 of 35 batch syntheses since 2026-11-01 carry a null headline (random picks match, the switch does the work, no buy signal). Each idea is tested as one concentrated book through the full simulator; on the only two arms with a 200-random-twin reading, twins with identical dates and weights spread about 3.6 pts/yr (p5-p95), larger than a typical signal effect. Only 2 of 364 eligible dev trials have a yardstick reading. engine/src/seer_engine/lab/ has ~a dozen book-level de-noising modules (control_draw, control_shape, control_weight, dressing, shortfall, exposure, gate_probe, timing, turnover, twins, yardstick) and no cross-sectional signal evaluator.

Proposed scope:
1. A signal registry: a signal is a pure function (symbol, data_date, look-ahead-safe history/market) -> score, one per file or entry, pre-registered by commit like methods are.
2. A new `lab panel` command: for every index member and month in the dev window (ends 2015-10-16, never the test window), signal value and next-month return; reports top-minus-pool spread and rank correlation with error bars, split by era (2009-2015 on its own), raw and after removing momentum, beta, size and volatility; a false-discovery correction across all registered signals; runs on both the dev store and the survivorship store (engine/.research-sv) and reports both.
3. First job: replay the signals of the already-run stock-signal methods (lab/methods/mNNNN_*.py, family like 'stock-%') through the panel in one pass, producing a ranked map of the explored space. Decide how to extract the ranking function from existing Allocators without changing any config digest or frozen record.
4. Stage two unchanged: the book lab (pre-registration, hard gate, DSR, yardstick, test budget, Gotrade fees) runs only signals that clear the panel, on one fixed chassis. Define the panel bar and where it is enforced (lab idea / lab run refusal, exit 2).
5. Skill changes: .claude/skills/sera-the-explorer and .claude/skills/explore-and-experiment-new-method — signal ideas go through the panel instead of one agent session + worktree + tmux window each; drop the "queue at least one next idea" rule and the one-per-family slate rule for signal ideas; one synthesis per panel sweep rather than per four methods; route the 138 queued stock-signal ideas through the panel.
6. Persistence and site: decide whether panel results live in lab.sqlite (new append-only table + migration, snapshot in web/data/lab.json, CI row-for-row check) and how /sera shows them in plain language.

Constraints: closed records are frozen (existing lab rows, config digests, registry); shared lab params cannot gain a field; lookback cap of 473 bars on History in the smoke fixture; fundamentals panel starts 2009; market-cap coverage is partial; research store memory ~1.79 MB/symbol on a 15 GB laptop; tests must never reach production; verify-seer feature map must be updated for user-facing changes; plain-language text for the owner. Open risks to analyse: survivorship in the dev store, look-ahead in the panel builder, multiple-testing policy interaction with the existing N policy and DSR, whether panel looks should count against N, and how a panel "no" on the whole space is recorded as a finding.

### User-Provided Context

Earlier in the conversation the owner said: "i am fine if you want to propose a huge refactor, a huge architectural change, removing a big module, cutting some big chunk off.. i just care about results, i dont care about how much effort it would take, how much tokens it would cost. just BE RUTHLESS".

### User-Provided Files

None marked with `@`.

### Requirement IDs

| ID | What the user asked for (verbatim) |
|---|---|
| R1 | A signal registry: a signal is a pure function (symbol, data_date, look-ahead-safe history/market) -> score, one per file or entry, pre-registered by commit like methods are. |
| R2 | A new `lab panel` command: for every index member and month in the dev window (ends 2015-10-16, never the test window), signal value and next-month return; reports top-minus-pool spread and rank correlation with error bars, split by era (2009-2015 on its own), raw and after removing momentum, beta, size and volatility; a false-discovery correction across all registered signals; runs on both the dev store and the survivorship store (engine/.research-sv) and reports both. |
| R3 | First job: replay the signals of the already-run stock-signal methods (lab/methods/mNNNN_*.py, family like 'stock-%') through the panel in one pass, producing a ranked map of the explored space. Decide how to extract the ranking function from existing Allocators without changing any config digest or frozen record. |
| R4 | Stage two unchanged: the book lab (pre-registration, hard gate, DSR, yardstick, test budget, Gotrade fees) runs only signals that clear the panel, on one fixed chassis. Define the panel bar and where it is enforced (lab idea / lab run refusal, exit 2). |
| R5 | Skill changes: .claude/skills/sera-the-explorer and .claude/skills/explore-and-experiment-new-method — signal ideas go through the panel instead of one agent session + worktree + tmux window each; drop the "queue at least one next idea" rule and the one-per-family slate rule for signal ideas; one synthesis per panel sweep rather than per four methods; route the 138 queued stock-signal ideas through the panel. |
| R6 | Persistence and site: decide whether panel results live in lab.sqlite (new append-only table + migration, snapshot in web/data/lab.json, CI row-for-row check) and how /sera shows them in plain language. |

#### Acceptance Criteria

| ID | Pattern | Criterion |
|---|---|---|
| R1.1 | ubiquitous | THE SYSTEM SHALL discover every `engine/src/seer_engine/lab/signals/sNNNN_<slug>.py` module exporting `SIGNAL`, and its contract test SHALL fail for a signal that is impure, repeats an id, or returns a different score when bars dated after the data date change. |
| R1.2 | unwanted | IF a signal file named to `lab panel` is uncommitted or modified in the working tree THEN THE SYSTEM SHALL exit 2 and record nothing. |
| R2.1 | event | WHEN `lab panel SNNNN` runs THE SYSTEM SHALL record, for the dev store and the survivorship store and for each era (whole window, before 2009, 2009-2015), the months measured, the mean monthly rank correlation and its t-statistic, the annualised top-bucket-minus-pool spread and its t-statistic, and the slope on next-month return after controlling for momentum, beta, size and volatility with its t-statistic. |
| R2.2 | unwanted | IF the store handed to `lab panel` declares any window other than dev, or the survivorship store is missing, THEN THE SYSTEM SHALL exit 2 and record nothing. |
| R2.3 | event | WHEN `lab panel-map` runs THE SYSTEM SHALL print every recorded panel ranked by its controlled slope, each with a verdict computed by a Benjamini-Hochberg correction across all distinct recorded panels. |
| R3.1 | event | WHEN `lab panel-replay` runs THE SYSTEM SHALL record one pick-set panel per recorded dev candidate of every method whose family begins `stock-`, obtained by calling the candidate's own allocator at each month end with nothing held, while leaving every `trials` row, config digest and recorded source sha byte-identical. |
| R3.2 | state | WHILE two recorded panels hold the identical pick set in every month THE SYSTEM SHALL count them as one panel in the correction and show the later one as a twin of the first in `lab panel-map`. |
| R4.1 | unwanted | IF `lab run` is given a method with a candidate that picks index members and the method names neither a registered signal whose published panel verdict clears on the current dev store nor a panel exemption THEN THE SYSTEM SHALL exit 2, record nothing and spend no N. |
| R4.2 | unwanted | IF a method names a signal and any of its non-control candidates is not that signal's standard-chassis book THEN THE SYSTEM SHALL exit 2 and record nothing. |
| R4.3 | ubiquitous | THE SYSTEM SHALL leave the luck gate's N unchanged by any `lab panel`, `lab panel-replay` or `lab panel-map` run. |
| R5.1 | ubiquitous | THE SYSTEM SHALL carry, in `.claude/skills/sera-the-explorer/SKILL.md`, a sweep procedure in which one session writes and commits several signal files, runs `lab panel` on them, writes one synthesis for the sweep, and launches a child session only for a signal that cleared or for an idea that is not a stock-picking signal. |
| R5.2 | ubiquitous | THE SYSTEM SHALL carry, in `.claude/skills/explore-and-experiment-new-method/SKILL.md`, the rule that a stock-picking idea is written as a signal file and panelled before any method file, with the queue-one-idea rule and the one-per-family slate rule stated as not applying to signal ideas, and the procedure that turns a queued stock-signal idea row into a signal. |
| R6.1 | event | WHEN `lab stage` or `lab export-json` runs THE SYSTEM SHALL write a `panel` key into `web/data/lab.json` that the snapshot test byte-compares against the export of `lab/lab.sqlite`. |
| R6.2 | event | WHEN the owner opens `/sera/signals` THE SYSTEM SHALL show the ranked signal map with each row named by what the signal does, its verdict in everyday words, and no method ids, digests or code. |
| R6.3 | unwanted | IF the lab database holds no panel tables or no panel rows THEN THE SYSTEM SHALL publish an empty `panel` list and `/sera/signals` SHALL render an empty state. |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** The lab's only instrument is a book backtest: `lab run` simulates 1-6 concentrated books per idea through `book_runner.run_book` and judges each curve. There is no code path that asks the prior question, "does this ranking order next-month returns across the pool?". The request adds that path as a separate, cheaper stage with its own registry, its own record and its own multiple-testing rule, and makes the existing book stage refuse a stock-picking method whose signal has not cleared it.

**Success Criteria.** A signal is a committed file; one command measures it on both stores and three eras and records the result append-only; the 350-odd already-run stock-signal methods are replayed into the same table without touching their records; `lab run` refuses an unpanelled stock picker; the site shows the map; the two Sera skills describe the new flow.

**Key Considerations.**
- *Look-ahead.* The book runner's prepared path relies on a contract test, not a cut (`strategies/allocator.py:8-12`). A panel that calls a new score function can enforce the cut itself by handing only `h.upto(d)` views.
- *Survivorship.* The dev store has no delisted names; `engine/.research-sv` has them back but is the uncleaned tape and carries a purpose marker that `lab run` refuses (`runner.survivorship_refusal`). The panel must read both and treat a name whose bars stop mid-month.
- *Total return.* No per-stock total-return helper exists. `tree_rank.forward_returns` is price-only (`lab/tree_rank.py:575-595`). Dividends are in `ResearchData.dividends`.
- *Multiple testing.* DSR's N is `count(DISTINCT method_id) FROM trials WHERE window='dev'` (`npolicy.py:156-160`). Panel rows are not trials, so they do not enter N unless code is added to make them.
- *Frozen records.* `config_digest` covers a `Candidate`'s rules, allocator id and params (`lab/method.py:43-51`); `Method` fields are outside it. A method file's sha is compared against `store.latest_source_sha` only for that file.
- *The 473-bar cap.* Every lab allocator is driven over `labkit.smoke_market` (473 sessions); `control_draw.FIXTURE_BARS = 473`.
- *Schema policy.* `store.py:612-615`: an additive table whose reader answers None when absent needs no version bump; a bump "is a one-way door for every parallel checkout".
- *Snapshot.* Any new snapshot key changes the byte-compared export, so `web/data/lab.json`, `lab/lab.sqlite` (tables are created on connect) and the web `version` literal move together.

**Assumptions.**
- "Month" means the last NYSE session of each calendar month in the dev window; the forward month ends at the next such session.
- "Size" is controlled with log 20-day dollar volume, which every pool row has; `Market.market_value` covers about 57% of dev member-days (explore skill, step 3) and is not used as a control.
- The 138 queued stock-signal ideas are routed by the skills (an operational procedure), not by a one-off script.
- The production replay run writes the shared `lab/lab.sqlite`; it is run from the main checkout after landing, by Sera's updated preflight, and proved before landing on a copy.

---

## Analysis Scope

### Explicitly Mentioned Files
- `.claude/skills/sera-the-explorer/SKILL.md` (268 lines)
- `.claude/skills/explore-and-experiment-new-method/SKILL.md` (615 lines), `method_template.py`
- `engine/src/seer_engine/lab/methods/mNNNN_*.py` (412 method modules)
- `lab/lab.sqlite`, `web/data/lab.json`

### Discovered Related Files
- `engine/src/seer_engine/research.py` — store loader, windows, fingerprints
- `engine/src/seer_engine/backtest/market.py` — `Market`, `Membership`, `MarketSeries`, `DividendCalendar`, `ShareCounts`
- `engine/src/seer_engine/backtest/dev.py`, `backtest/book_runner.py` — candidate run, data-date cut
- `engine/src/seer_engine/strategies/allocator.py`, `strategies/base.py`, `strategies/f_factor.py`, `strategies/indicators.py`
- `engine/src/seer_engine/lab/method.py`, `runner.py`, `hardgate.py`, `store.py`, `npolicy.py`, `yardstick.py`, `tree_rank.py`, `twins.py`
- `engine/src/seer_engine/commands/lab.py`, `commands/backtest_dev.py` (`registry_problem`)
- `engine/tests/labkit.py`, `allocatorkit.py`, `test_lab_methods.py`, `test_lab_snapshot.py`, `test_lab_books.py`, `test_lab_gate_wording.py`, `conftest.py`
- `web/lib/sera/{types,lab,derive,fixture}.ts`, `web/lib/sera/lab.test.ts`, `web/app/sera/**`, `web/components/sera/**`, `web/app/sera/overview.test.ts`
- `.claude/skills/verify-seer/features/{README,lab-cli,sera}.md`
- `docs/runbooks/yardstick-backfill.md`, `docs/runbooks/survivorship-store.md`

---

## Current Dataflow

### Entry Point: `python -m seer_engine lab run MNNNN`

**Location:** `engine/src/seer_engine/commands/lab.py:2057` (`_run`), dispatched through `_HANDLERS` (`:4780-4818`) from `run()` (`:1140-1148`).
**Trigger:** CLI. `run()` always calls `store.connect(args.db)`, which creates tables, migrates and therefore rewrites the file even for report commands.
**Validation:** `LabError` -> exit 2; any other exception -> exit 1.

### Processing Chain

1. `research.declared_purpose(store)` — a store with a purpose marker (the survivorship store) is refused (`lab.py:2065-2070`).
2. `method.discover()` (`lab/method.py:211-231`) — `pkgutil.iter_modules` over `seer_engine.lab.methods`, module name `m(\d{4})_[a-z0-9_]+`, `METHOD` must be a `Method`.
3. `runner.preflight` (`runner.py:283-360`) — `registry_problem(path)` (committed and clean, `commands/backtest_dev.py:486`), real-fee check, status must be idea/registered unless `--amend`, parent exists, `store.has_trial(digest, "dev")` refuses a repeated configuration.
4. `research.load_store(store)` (`research.py:1334-1447`) — verifies manifest sha256s and fingerprint, refuses any row after `window.end`, builds `Market`. About 11-12 s and roughly 1 GB.
5. `hardgate.pin_dev_store` (D10, `hardgate.py:1406-1456`) — price fingerprint must match the benchmark trial's.
6. `runner.preflight_data` — required optional files and coverage.
7. `dev.run_registry` -> `run_candidate` -> `book_runner.run_book`: per session `members = market.membership.members_on(data_date)` (`book_runner.py:421`), then `allocator.targets_prepared(prepared, members, data_date, mine, params)` (`:428`).
8. `_measure_yardsticks` — 200 random twins per eligible non-control arm, fork pool (`yardstick.py:637-649`), about 200 s per arm at `--jobs 2`.
9. One transaction: trials, moments, funding, provenance, roles, yardstick, fold verdict, status, `mark_seen` (`runner.py:940-1071`).

### How a ranking is produced today

- The protocol is `Allocator.targets(history, members, data_date, held, params) -> tuple[Target, ...]` (`strategies/allocator.py:57-95`): targets in rank order, already cut to the book's width. No protocol member returns a score for every pool member.
- 350 of 412 method files define their own `targets`; 302 reference `FACTOR`/`f_factor`; 87 define a separately named score/rank/signal function. There is no shared `score(symbol) -> float` seam; sub-families import helpers from each other (`m0509.scored_names`, `m0503.scored_names`, `m0117.liquid_rows`).
- `f_factor.FactorPrepared.rows_on(members, data_date, params)` (`f_factor.py:403-421`) returns `FactorRow(symbol, close, momentum, vol, dollar_volume)` for every member that passes the F4 screen (`_eligible_mask`, `:180-207`: has a bar on d, enough bars, finite features, vol > 0, 20-day dollar volume > 20,000,000, close >= 5). `tree_rank.SCREEN = N20_NOTREND` is that screen with no trend switch (`tree_rank.py:205-206`).
- `tree_rank.py` holds the only cross-section machinery: `month_ends(start, end)` (`:359`), `build_section` (`:531`), `forward_returns` (`:575-595`, price only).

### Data Persistence

**Database:** `lab/lab.sqlite`, opened by `store.connect` (`store.py:900-931`). `DB_PATH = SEER_LAB_DB or COMMITTED_DB` (`:124`). Tables are declared as `_<NAME>_TABLE` / `_<NAME>_TRIGGERS` constants pasted into `_SCHEMA` (`:741-889`). `trial_yardstick` (`:668-693`) and `trial_roles` were added with `CREATE TABLE IF NOT EXISTS` and no version bump; readers guard with `_has_yardstick_table` (`:3375`). `SCHEMA_VERSION = "8"` (`:126`).
**Snapshot:** `store.snapshot(conn)` (`:4166-4324`) -> `snapshot_json` -> `write_snapshot` -> `web/data/lab.json`. Top-level keys in order: `version, asOf, gate, data, summary, benchmark, books, methods, trials, insights, ideasSeen, paper`. `SNAPSHOT_VERSION = 8` (`:3898`). The file is 23,607,912 bytes.
**Check:** `engine/tests/test_lab_snapshot.py:1346` byte-compares the committed JSON against the export of the committed DB opened read-only.

### Exit Points
- stdout report; `trials` and side-table rows; `methods.status`; exit code 0/1/2.
- `/sera` reads `web/data/lab.json` through a static import (`web/lib/sera/lab.ts:5`), typed by `LabSnapshot` (`web/lib/sera/types.ts:3-84`, `version: 8`).

---

## Key Data Structures

### `History` — `strategies/base.py:33-92`
Frozen dataclass: `symbol`, `dates` (datetime64[D]), float64 `open/high/low/close/volume`. `upto(d)` returns views of bars dated on or before `d`; `index_of(d)`.

### `Market` — `backtest/market.py:535-722`
`history`, `membership` (`members_on(d)`), `fx`, `fundamentals`, `dividends` (`known_on(symbol, d)`), `series` (`value_on`, `upto`), `shares` (`shares_on`, `market_value`).

### `ResearchData` — `research.py:262-280`
`market`, `dividends: dict[str, dict[date, Decimal]]`, `spy_dividends`, `fingerprint`, `price_fingerprint`, `manifest`, `window`, `purpose`.

### `Method`, `Amendment` — `lab/method.py:54-205`
`Method(id, name, family, source_kind, source_ref, hypothesis, expected_failure, candidates, parent_id, seen_keys, amendments)`. `config_digest(c)` hashes rules, allocator id and params only.

### `YardstickRow` and its table — `store.py:668-693, :3314-3487`
The worked example of an additive, append-only side table with a dataclass, `*_COLUMNS`, a guarded reader, a validating insert and a snapshot projection (`_snapshot_yardstick`, `:4007-4041`).

---

## Dependencies

### Configuration / Environment / External Services
- `SEER_LAB_DB`, `SEER_RESEARCH_STORE`, `SEER_SV_STORE` (`commands/lab.py:207-210, :322, :818`).
- Stores present on this machine: `engine/.research`, `engine/.research-sv`, `engine/.research-test`. A worktree has none; commands point at the main checkout's.
- `engine/pyproject.toml`: numpy >= 2, pandas >= 2.2, scikit-learn (scipy arrives with it but is not declared).
- No external service is involved; tests are isolated by `conftest._isolated_env` (Neon only; the lab DB is reached read-only by convention).

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `_SCHEMA`, `_YARDSTICK_TABLE`, `_YARDSTICK_TRIGGERS` | `engine/src/seer_engine/lab/store.py:668-693, :741-889` | def | lab |
| `snapshot`, `SNAPSHOT_VERSION` | `engine/src/seer_engine/lab/store.py:3898, :4166-4324` | def | lab |
| snapshot key list / version asserts | `engine/tests/test_lab_snapshot.py:673, :945-947`; `engine/tests/test_lab_books.py:315` | test | tests |
| `LabSnapshot.version`, key list | `web/lib/sera/types.ts:16`; `web/lib/sera/lab.test.ts:9-14`; `web/app/sera/overview.test.ts:103-104` | def · test | web |
| engine/web vocabulary pin | `engine/tests/test_lab_gate_wording.py:315-321` | test | tests |
| `Method` dataclass | `engine/src/seer_engine/lab/method.py:117-205` | def | lab |
| `runner.preflight` | `engine/src/seer_engine/lab/runner.py:283-360` | def | lab |
| hard-gate decisions (D10, D14, D17, D19, D20) | `engine/src/seer_engine/lab/hardgate.py` | def | lab |
| `add_arguments`, `_HANDLERS` | `engine/src/seer_engine/commands/lab.py:285-287, :4780-4818` | def | commands |
| `lab names` (store-loading report template) | `engine/src/seer_engine/commands/lab.py:495-533, :2948-2997` | def | commands |
| `registry_problem` | `engine/src/seer_engine/commands/backtest_dev.py:486` | def | commands |
| method contract tests | `engine/tests/test_lab_methods.py:61-189` | test | tests |
| `smoke_market`, `SMOKE_FIRST` | `engine/tests/labkit.py:21-60` | def | tests |
| `month_ends`, `forward_returns`, `SCREEN` | `engine/src/seer_engine/lab/tree_rank.py:205, :359, :575` | def | lab |
| `FactorPrepared.rows_on`, `prepare_factor` | `engine/src/seer_engine/strategies/f_factor.py:403-424` | def | strategies |
| `return_window`, `stdev_return_window` | `engine/src/seer_engine/strategies/indicators.py:161, :188` | def | strategies |
| `prepare_for` | `engine/src/seer_engine/strategies/allocator.py:116-135` | def | strategies |
| Sera routes and nav | `web/app/sera/*/page.tsx`, `web/components/sera/SeraNav.tsx` | def | web |
| feature map | `.claude/skills/verify-seer/features/{README,lab-cli,sera}.md` | doc | skills |
| method template | `.claude/skills/explore-and-experiment-new-method/method_template.py` | doc | skills |
| "queue at least one next idea" | `.claude/skills/explore-and-experiment-new-method/SKILL.md:10-12, :308-313` | doc | skills |
| slate rules, per-batch synthesis | `.claude/skills/sera-the-explorer/SKILL.md:82-120, :205-245, :252` | doc | skills |

---

## Impact Points (files that WILL need changes)

1. `engine/src/seer_engine/lab/panel.py` (new) — panel builder and statistics. Phase 1.
2. `engine/src/seer_engine/lab/signal.py`, `lab/signals/` (new) — registry, seed signals. Phase 1.
3. `engine/tests/test_lab_panel.py`, `test_lab_signals.py` (new). Phase 1.
4. `engine/src/seer_engine/lab/store.py` — two additive tables, insert/read, snapshot `panel` key, `SNAPSHOT_VERSION`. Phase 2.
5. `engine/src/seer_engine/lab/panel_verdict.py` (new) — correction and published verdict. Phase 2.
6. `engine/tests/test_lab_snapshot.py`, `test_lab_books.py`, new `test_lab_panel_record.py`. Phase 2.
7. `web/lib/sera/types.ts`, `lab.test.ts`, `web/app/sera/overview.test.ts`, `web/data/lab.json`, `lab/lab.sqlite` — snapshot version and key. Phase 2.
8. `engine/src/seer_engine/commands/lab.py` — `panel`, `panel-map`, `next-signal-id`. Phase 3. `panel-replay`. Phase 4.
9. `engine/src/seer_engine/lab/panel_replay.py` (new), `docs/runbooks/signal-panel.md` (new). Phase 4.
10. `engine/src/seer_engine/lab/method.py`, `runner.py`, `hardgate.py`, new `lab/signal_book.py`, `method_template.py`, new signal template. Phase 5.
11. `web/app/sera/signals/` (new), `web/components/sera/SeraNav.tsx`, `web/lib/sera/` helpers, `.claude/skills/verify-seer/features/sera.md`. Phase 6.
12. `.claude/skills/sera-the-explorer/SKILL.md`, `.claude/skills/explore-and-experiment-new-method/SKILL.md`, `CLAUDE.md`, `README.md`. Phase 7.
13. `.claude/skills/verify-seer/features/signal-panel.md` (new, Phase 3; appended by Phase 4), `lab-cli.md` (Phase 5).

**This document describes. The plan files prescribe.**

# Plan: Random-twin yardstick for the method lab

**Slug:** random-twin-yardstick
**Date:** 2026-11-13 12:54 WIB
**Analysis:** `.workflows/analyze/20261113-125454-Y7RT_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/random-twin-yardstick`
**Branch:** `feature/random-twin-yardstick` (base: `origin/main` @ `f83fb237`)
**Phases:** 5
**Status:** planned
**Coordinator:** —

---

## Why

The user's request, verbatim:

> you idea so we can implement them robustly

"You idea" is the one recommendation of the codebase review that preceded it in the same session,
and "them" its three numbered parts, verbatim:

> 1. **A random-book yardstick per setup.** For each combination of pool, book size, cadence,
>    weighting and safety switch, run a few hundred random books once and cache the distribution.
>    These count against nothing.
> 2. **Judge ideas against it.** An arm passes only if it beats roughly the top tenth of random
>    books on its own setup, in place of today's "beats SPY and clears the luck score".
> 3. **Derive status from treatment arms only.** Arm roles already exist (the hard gate reads them
>    to refuse promoting a control); the status line just ignores them.

The review's reason: on the committed lab, 42 of 45 dev runs of deliberately meaningless books beat
SPY and 14 cleared the whole screen, while 362 of 2,051 researched runs did. Of the 256 arms that
read eligible at today's bars, 64 are control arms; of 182 `dev-eligible` methods, 94 have an
eligible non-control arm. The screen grades the shape of a book, not the idea in it. The review
also said the change "needs a dated owner revision and a re-judging pass, not a quiet code change".

## Requirements

| ID | What the user asked for (verbatim) | Phases |
|---|---|---|
| R1 | "you idea so we can implement them robustly" — part 1: "A random-book yardstick per setup. For each combination of pool, book size, cadence, weighting and safety switch, run a few hundred random books once and cache the distribution. These count against nothing." | 2, 3 |
| R2 | "you idea so we can implement them robustly" — part 2: "Judge ideas against it. An arm passes only if it beats roughly the top tenth of random books on its own setup, in place of today's 'beats SPY and clears the luck score'." | 4, 5 |
| R3 | "you idea so we can implement them robustly" — part 3: "Derive status from treatment arms only. Arm roles already exist (the hard gate reads them to refuse promoting a control); the status line just ignores them." | 1 |

### Acceptance Criteria

| ID | Pattern | Criterion | Phases | Journeys |
|---|---|---|---|---|
| R1.1 | event | WHEN `lab yardstick <method>` is run for a recorded dev arm that holds picked stocks THE SYSTEM SHALL simulate `YARDSTICK_DRAWS` random twin books that replay that arm's own decisions (same dates, weights, entries and exits) with every picked name replaced by a randomly drawn index member of similar trading size, and record the share of twins the arm out-earned. | 2, 3 | P2.J1, P2.J2, P2.J3, P3.J2, P3.J5 |
| R1.2 | ubiquitous | THE SYSTEM SHALL record a yardstick measurement without inserting a `trials` row, changing the luck count N, or spending a test-window look. | 3 | P3.J2, P3.J5 |
| R1.3 | unwanted | IF the twins' median trade count or turnover falls outside 0.50x–2.00x of the arm's own THEN THE SYSTEM SHALL record the measurement as `unmatched`, which never counts as clearing the yardstick. | 2 | P2.J4 |
| R1.4 | unwanted | IF the arm's decisions hold no picked stock at all (an ETF-only or cash-only book) THEN THE SYSTEM SHALL record the yardstick as `not-applicable` and simulate no twins. | 2 | P2.J5 |
| R1.5 | ubiquitous | THE SYSTEM SHALL produce the identical yardstick result for the same arm on the same research store, whatever the `--jobs` value, and SHALL NOT append a second row when the measurement is repeated. | 2, 3 | P2.J6, P3.J1, P3.J2, P3.J3, P3.J5 |
| R1.6 | unwanted | IF the arm's trial was recorded on the loaded store and re-running the arm does not reproduce its recorded trade count and return THEN THE SYSTEM SHALL refuse with exit code 2 and record nothing. | 3 | P3.J4, P3.J5 |
| R2.1 | event | WHEN `lab run` records a non-control arm that clears every other screen condition THE SYSTEM SHALL measure its yardstick before recording and record the arm eligible only if it out-earned at least `YARDSTICK_MIN_PERCENTILE` (0.90) of its twins. | 4 | P4.J1, P4.J2 |
| R2.2 | state | WHILE a dev arm's latest yardstick measurement is below the bar or `unmatched` THE SYSTEM SHALL report that arm not eligible in `store.verdict`, with the yardstick label in its failure list. | 4 | P4.J3, P4.J4 |
| R2.3 | unwanted | IF `lab promote` is asked to promote a method whose chosen arm has no measured yardstick that clears the bar (and is not `not-applicable`) THEN THE SYSTEM SHALL refuse with exit code 2 and write nothing. | 4 | P4.J5, P4.J6 |
| R2.4 | event | WHEN the lab snapshot is exported THE SYSTEM SHALL publish each arm's role and yardstick reading, and the method page SHALL show the yardstick as a seventh condition in plain words with no ids or code. | 5 | P5.J1, P5.J2, P5.J3, P5.J4, P5.J5, P5.J6 |
| R3.1 | event | WHEN `lab run` finishes a new method THE SYSTEM SHALL set its status to `dev-eligible` only if at least one non-control arm is eligible, and to `rejected` otherwise. | 1 | P1.J1 |
| R3.2 | state | WHILE an arm is recorded as a control THE SYSTEM SHALL report it not eligible in `store.verdict` and SHALL never choose it in `store.best_dev_eligible`. | 1 | P1.J2, P1.J5 |
| R3.3 | event | WHEN `lab reevaluate --demote` is run on a `dev-eligible` method that has no eligible non-control arm at today's bars THE SYSTEM SHALL move it to `rejected`, append a dated note to its analysis, and leave every trial row untouched. | 1 | P1.J4, P1.J6 |
| R3.4 | event | WHEN `lab roles --backfill` is run THE SYSTEM SHALL record the role of every recorded dev arm whose method file can be read, once, and SHALL skip arms it cannot read without failing. | 1 | P1.J3, P1.J6 |

## Scope

**In scope:**

- A role record per trial, role-aware eligibility and status, a narrow door from `dev-eligible`
  back to `rejected` (phase 1).
- A pure random-twin engine that works on any book-engine arm by replaying its decisions (phase 2).
- A yardstick record in the lab database and the `lab yardstick` command (phase 3).
- The yardstick as a seventh screen condition at `lab run`, in `store.verdict` and at `lab promote`,
  with the dated design revision and the skill and runbook text that goes with it (phase 4).
- Snapshot fields and the Sera pages that show them (phase 5).

**Out of scope:**

- Re-judging the arms the lab already holds. That writes the shared `lab/lab.sqlite` on `main` and
  is lab operation, not code. Phase 4 delivers the runbook; see `## Next`.
- Removing or loosening any existing condition (`beats SPY TR`, drawdown, PF, trades, owner inputs,
  DSR) or the luck count N. See Decision D2.
- The §1 real-money bar.
- Bracket-engine (`DESIGN_V0`) candidates: they read `not-applicable`.
- The hand-written control arms in recorded method files, `lab/control_draw.py` and
  `lab/control_weight.py`. They stay as they are and stay useful as controls.
- The red CI pins, the stale index membership and the Vercel build noise the review also listed.

## Invariants

1. The tree imports, `ruff check engine` is clean and every lab test file passes at the end of each
   phase. Web phases also pass `npx tsc --noEmit && npm test`.
2. **No phase commits `lab/lab.sqlite`.** Tests and proofs use temporary databases (`labkit`,
   `tmp_path`) or the `verify-seer` lab copy. If a command touched the committed file, restore it
   with `git checkout -- lab/lab.sqlite` before committing. `web/data/lab.json` is derived: only
   phase 5 regenerates it, and the integrator regenerates it again at merge instead of merging it.
   Every phase builds its own `engine/.venv` in this worktree and commits named paths only (each
   plan's **Commit** block).
   *Web label pin:* `web/lib/sera/lab.test.ts:56-70` fails once `lab.json` carries `not a control
   arm` or `beats 90% of random twins`; the set lands together and phase 5 teaches the web both. Phase
   5's export of the unmodified committed `lab/lab.sqlite` carries neither label (P5.J1 asserts it).
3. `store.SCHEMA_VERSION` stays `"8"`. New tables are additive `CREATE TABLE IF NOT EXISTS`
   statements in `_SCHEMA`, and every reader of a new table returns None when the table is absent,
   exactly as `funding_of` does. A version bump would break every parallel Sera checkout on connect.
4. No role or yardstick path inserts, updates or deletes a `trials` row, and `store.gate(conn).n`
   is the same before and after any of them.
5. On a database with no `trial_roles` row, no `trial_yardstick` row and no dev trial run on or
   after `store.YARDSTICK_SINCE`, `store.verdict` returns exactly what it returns today.
6. Recorded method files are frozen: none is edited. `control_draw` v1 and v2 function bodies are
   not edited.
7. The six existing screen conditions and the §1 real-money bar are untouched. The yardstick is a
   seventh condition.
8. Modules carry prose docstrings that say why. Text the owner reads uses plain words: no ids,
   digests or code. argparse help escapes `%` as `%%`.
9. Commit explicit file paths only. Never `git commit -a`.
10. Tests never reach production, the network, or the real research store.

## Interface Contract

Names every phase plans against. A planner may add private helpers; it may not rename these.

**Phase 1 — `lab/store.py`, `lab/runner.py`, `commands/lab.py`**

- Table `trial_roles(trial_n INTEGER PRIMARY KEY REFERENCES trials(n), role TEXT, source TEXT, measured TEXT)`,
  `role` checked against `control_shape.ROLES` (literal list in SQL), `source` in
  `('recorded','backfill')`, append-only triggers.
- `store.RoleRow`, `store.insert_roles(conn, rows)`, `store.role_of_trial(conn, trial_n) -> str | None`
  (None when the table or the row is absent).
- `store.CONTROL_LABEL = "not a control arm"`. `store.verdict` appends it, after the luck label,
  when `role_of_trial` is `"control"`. `runner.trial_rows` appends the same label to a control
  arm's recorded `failed`, so the record and the verdict agree on the run date.
- `store.TRANSITIONS` gains `("dev-eligible", "rejected")`.
- `store.TRIAL_ROLES`, `store.CONTROL_ROLE`, `store.ROLE_SOURCES`; `Ran.role: str | None = None`.
- `store.DEMOTION_MARKER = "Demoted under the "`, `store.demote_method(conn, method_id) -> Reevaluation`
  and `store.demote(conn, method_ids=None)`: the one door on that edge. `lab reevaluate --demote
  [MNNNN ...]` calls it; plain `lab reevaluate` never demotes. `store.Reevaluation` gains
  `eligible_now: tuple[str, ...] = ()` and `controls: int = 0`.
- `store.reevaluate_method`: a `rejected` method whose analysis carries `DEMOTION_MARKER` is also
  unblocked by a dev trial eligible under `verdict` today whose *recorded* `eligible` is 1 (the
  `_blocking` re-check still applies), so the demotion door is reversible (Decision D10).
- `store.unroled_dev_trials(conn, method_ids=None)`; `lab roles [MNNNN ...] [--backfill]`.

**Phase 2 — new `lab/yardstick.py`, no database import**

- `RULE_ID = "yardstick-v1"`, `DRAWS = 200`, `LIQUIDITY_BARS = 63`, `NEIGHBOUR_RANKS = 25`,
  `REPRODUCE_TOLERANCE = 1e-9`.
- `STATUS_MEASURED = "measured"`, `STATUS_NOT_APPLICABLE = "not-applicable"`, `STATUS_UNMATCHED = "unmatched"`, `STATUSES`.
- `Decision(data_date, members, targets, rank: bool = True)`; `Recorder(inner, rules)` (an
  `Allocator` and `MarketAware` wrapping another, logging every `targets_prepared` call, with
  `.decisions`); `Replay(inner, schedule, seed=None)` (an `Allocator` that returns a fixed schedule
  as-of a date).
- `seed_for(config_digest: str, i: int) -> int`; `fixed_symbols(candidate) -> frozenset[str]`;
  `record(market, dividends, spy_dividends, candidate, *, initial_idr, contributions) -> (decisions, DevRow)`.
- `twin_schedule(market, decisions, fixed, seed, *, ranks=None) -> dict[date, tuple[Target, ...]]`.
- `Measurement` (frozen dataclass): `status, draws, arm_rate, beaten, percentile, rates, trade_ratio,
  turnover_ratio, reproduced`. **Its `__post_init__` is the shape every later phase mirrors
  (Decision D11):** `not-applicable` is `draws=0, beaten=0, percentile=None, rates=(),
  trade_ratio=None, turnover_ratio=None`; `measured` and `unmatched` are `draws>=1,
  0<=beaten<=draws, percentile=beaten/draws`; `rates` are sorted floats; a bracket arm reads
  `not-applicable` with `reproduced=None` (Decision D12).
- `Unreproducible(Exception)`.
- `measure(market, dividends, spy_dividends, candidate, *, initial_idr, contributions, draws=DRAWS, jobs=1, expect=None) -> Measurement`.
  `expect` is `(trades, total_return)` from a recorded trial, or None.

**Phase 3 — `lab/store.py`, `commands/lab.py`**

- Table `trial_yardstick(trial_n, rule_id, store_fingerprint, status, draws, arm_rate, beaten, percentile, rates_json, trade_ratio, turnover_ratio, reproduced, git_sha, measured, PRIMARY KEY (trial_n, rule_id, store_fingerprint))`,
  append-only; `beaten` NOT NULL; CHECKs mirror `Measurement` (D11). `store.YARDSTICK_STATUSES`.
- `store.YardstickRow` and `YardstickRow.from_measurement(m, *, trial_n, rule_id, store_fingerprint,
  checked, git_sha, measured)` — **the one** reading-to-row constructor (phase 4 uses it with
  `trial_n=0`); `store.has_yardstick(conn, trial_n, rule_id, store_fingerprint) -> bool`;
  `store.insert_yardstick(conn, row) -> bool` (False when the key exists);
  `store.yardstick_of(conn, trial_n) -> sqlite3.Row | None` (the latest row; None when absent).
- `store.YARDSTICK_MIN_PERCENTILE = 0.90`, `store.YARDSTICK_LABEL = "beats 90% of random twins"`
  (derived from the constant), `store.yardstick_clears(row) -> bool | None` on **any mapping**
  (`sqlite3.Row`, `dict`, `dataclasses.asdict(YardstickRow)`)
  (True: measured at or above the bar, or not-applicable; False: below, or unmatched; None: no row).
- `store.yardstick_due(conn, trial, *, at=None) -> bool`: a dev row, not a control, whose
  `verdict(...).failed` is empty or holds only `YARDSTICK_LABEL`.
- `lab yardstick [MNNNN ...] [--arm CANDIDATE] [--pending] [--limit N] [--jobs J] [--store DIR] [--dry-run]`;
  `commands/lab.py:_positive_count` (the one `--jobs` validator, `lab run` reuses it) and
  `_yardstick_line(candidate_id, row, note)` (the one reading printer, `lab run` reuses it).

**Phase 4 — `lab/store.py`, `lab/runner.py`, `lab/hardgate.py`, `lab/prereg.py`, `commands/lab.py`, docs**

- `store.YARDSTICK_SINCE = "2026-11-14"` (ISO date, compared with `trials.run_at`).
- `store.verdict` appends `YARDSTICK_LABEL` last when `yardstick_clears` is False, or when it is
  None and every other condition passes and the trial's `run_at >= YARDSTICK_SINCE`. Label order in
  `verdict` and `runner.trial_rows`: owner conditions, luck label, `CONTROL_LABEL`, `YARDSTICK_LABEL`.
- `store._blocking(trial, funding=None, reading=None)`.
- `runner.run_method(..., yardstick_jobs: int = 1, measure=yardstick.measure)`: measures, before
  `begin_immediate`, every non-control arm that passes D8 and a provisional DSR;
  `runner.trial_rows(..., yardsticks=None)`; `Ran.yardstick` after `Ran.role`.
- `hardgate.yardstick_refusal`; `hardgate.check`: clause (D20) on the promoted variant, after D18
  and before D19, failing closed on no reading.
- `lab run --jobs J` (default 2). `labkit.stamp_yardstick` (test helper).
- `prereg.gate_text` names the yardstick bar in newly written pre-registrations (Decision D13).
- `docs/plans/2026-10-04-method-lab-design.md` §10, `docs/runbooks/yardstick-backfill.md`, and every
  skill line that lists the dev screen (grep-based, phase 4 Step 19d).

**Phase 5 — `lab/store.py` snapshot, `web/`**

- `SNAPSHOT_VERSION = 8`. Per trial: `role: string | null` and
  `yardstick: { status, percentile, draws, beaten, armRate, medianRate, tradeRatio } | null`
  (`beaten` null for a not-applicable reading). Gate block: `yardstickMin`, `yardstickDraws`.
- `CONDITION_KEYS` gains `'yardstick'`; a control arm is shown as a comparison book, not as a
  failed idea. `view.missInWords` puts the two new labels into plain words on the redone panel
  (Decision D15).

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Roles in the record, role-aware status and the demotion door | R3 | `engine/lab` | 5 | — | HARD | `.workflows/plan/random-twin-yardstick/phase-1.md` | P1-ENG-NI1B (done 2026-11-13) | — |
| 2 | The random-twin engine | R1 | `engine/lab` | 2 | — | HARD | `.workflows/plan/random-twin-yardstick/phase-2.md` | P1-ENG-3B9A (done 2026-11-13) | — |
| 3 | The yardstick record and `lab yardstick` | R1 | `engine/lab` | 4 | 1, 2 | NORMAL | `.workflows/plan/random-twin-yardstick/phase-3.md` | P1-ENG-M170 (done 2026-11-13) | — |
| 4 | The yardstick as a screen condition | R2 | `engine/lab` | 18 | 3 | HARD | `.workflows/plan/random-twin-yardstick/phase-4.md` | P1-ENG-VZXN (done 2026-11-13) | — |
| 5 | Snapshot and Sera pages | R2 | `web` | 24 | 4 | NORMAL | `.workflows/plan/random-twin-yardstick/phase-5.md` | P1-WEB-59NH | — |

Phases 1 and 2 share no file and may run concurrently. Phases 3, 4 and 5 are strictly sequential:
each edits files the one before it edited (`store.py`, `runner.py`, `commands/lab.py`, `lab-cli.md`),
and each later plan quotes those files as the earlier phase leaves them.

### Phase 1 — Roles in the record, role-aware status and the demotion door
**Satisfies:** R3
**Criteria:** R3.1, R3.2, R3.3, R3.4
**Owns:** the `trial_roles` table and its helpers; `CONTROL_LABEL` in `store.verdict` and in
`runner.trial_rows`; role rows written by `run_method`; the `dev-eligible → rejected` transition and
`store.demote_method`; the way back for a demoted method in `reevaluate_method` (D10); `lab roles`
and `lab reevaluate --demote`; their tests and the `lab-cli.md` feature-map entry.
**Does not touch:** anything named `yardstick`; `hardgate.py` (D18 stays as a second, independent
refusal); the snapshot; `web/`.
**Exit criteria:** a method whose only eligible arm is a control records `rejected`; a recorded
control reads not eligible and is never chosen by `best_dev_eligible`; `--demote` moves a stale
method and appends a dated note, and plain `lab reevaluate` takes it back once an arm clears again;
`--backfill` is idempotent; invariant 5 holds.

### Phase 2 — The random-twin engine
**Satisfies:** R1
**Criteria:** R1.1, R1.3, R1.4, R1.5
**Owns:** the new module `lab/yardstick.py` and `tests/test_lab_yardstick.py`. Pure: a market, a
candidate and a seed in, a `Measurement` out.
**Does not touch:** `store.py`, `runner.py`, `commands/`, the database, `control_draw.py`.
**Exit criteria:** on a synthetic market, a recorded-and-replayed arm reproduces itself exactly; a
twin has the arm's decision dates and weights and none of its picked names by construction; the
result is identical at `jobs=1` and `jobs=2`; an ETF-only arm is `not-applicable`; a forced shape
mismatch is `unmatched`.

### Phase 3 — The yardstick record and `lab yardstick`
**Satisfies:** R1
**Criteria:** R1.1, R1.2, R1.5, R1.6
**Owns:** the `trial_yardstick` table and its helpers (`YardstickRow.from_measurement`,
`has_yardstick`, `insert_yardstick`, `yardstick_of`); `YARDSTICK_MIN_PERCENTILE`, `YARDSTICK_LABEL`,
`yardstick_clears`, `yardstick_due`; the `lab yardstick` command with `_positive_count` and
`_yardstick_line`, which phase 4 reuses; their tests and the `lab-cli.md` entry.
**Does not touch:** `store.verdict`, `runner.run_method`, `hardgate.py`, the snapshot, `web/`.
**Exit criteria:** `lab yardstick M…` on a fixture lab writes one row per due arm and none on a
second run; the trial count and `gate(conn).n` do not move; a non-reproducing arm exits 2 with
nothing written; a not-applicable (bracket) reading is recorded with `reproduced` NULL; every shape
phase 2's `Measurement` admits is a row `insert_yardstick` accepts.

### Phase 4 — The yardstick as a screen condition
**Satisfies:** R2
**Criteria:** R2.1, R2.2, R2.3
**Owns:** the yardstick condition in `store.verdict` and `YARDSTICK_SINCE`; measurement inside
`runner.run_method` before the write lock and the label in `trial_rows`; the clause in
`hardgate.check`; the yardstick clause in `prereg.gate_text`; the `lab run` wiring; design §10; the
backfill runbook; every skill and `CLAUDE.md` line that lists the dev screen (grep-based: explore,
Sera, stale-page skills); `labkit.stamp_yardstick` and the clearing readings in every fixture that
promotes; their tests and the `lab-cli.md` entry.
**Does not touch:** `lab/yardstick.py`'s draw rule; the snapshot; `web/`; committed pre-registration
files.
**Exit criteria:** a fixture arm that clears the other six conditions and loses to its twins
records not eligible and its method `rejected`; an old arm flips in `verdict` once a failing row
exists; `lab promote` refuses an unmeasured arm; a newly written pre-registration names the
yardstick; invariant 5 holds.

### Phase 5 — Snapshot and Sera pages
**Satisfies:** R2
**Criteria:** R2.4
**Owns:** the snapshot fields and `SNAPSHOT_VERSION`; `web/lib/sera` types, derive, glossary,
fixture and tests; the method page's seventh condition and the comparison-book treatment of control
arms; the how page's wording; the redone panel's plain words for the two new labels; the
regenerated `web/data/lab.json`; `sera.md` in the feature map.
**Does not touch:** any gate logic; `lab/lab.sqlite`; skill text (phase 4).
**Exit criteria:** the snapshot test and the JSON sync test pass; the method page shows the
yardstick row in plain words in both themes at phone and desktop widths; a row with no reading says
so and is never drawn as a pass; no owner-facing text prints either new engine label raw.

## Reconciliation Log

| Conflict | Phases | Resolution |
|---|---|---|
| Gap: the demotion door had no way back. `reevaluate_method` unblocks only trials recorded `eligible = 0`, so a method demoted on a recorded-eligible arm could never return, and the Rollback sentence was false | 1 | Phase 1 Step 9b: a rejected method whose analysis carries `DEMOTION_MARKER` is also unblocked by a trial eligible under `verdict` today with recorded `eligible = 1` (`_blocking` still applies); one docstring sentence; test `test_plain_reevaluate_takes_a_demoted_method_back_when_its_arm_clears_again` (P1.J6). Rollback sentence kept, now true. Decision D10 |
| Contract drift: phase 2 changed `Decision` (+`rank`), `Recorder(inner, rules)`, `twin_schedule(..., *, ranks=None)`, added `record`, `fixed_symbols`, `REPRODUCE_TOLERANCE`, `STATUSES`, and the draw also excludes the names the arm picks at that decision | 2, index | Accepted, all additive. Index Interface Contract and Decision D8's wording updated. Phases 3 and 4 call only `measure`, `Measurement`, `RULE_ID`, `DRAWS`, `STATUS_*`, `Unreproducible`, whose signatures did not change |
| Contract drift / broken build: a not-applicable reading's `beaten` was 0 in phase 2's `Measurement.__post_init__`, NULL in phase 3's CHECK and `insert_yardstick`, None in phase 4's `_reading`/`stamp_yardstick` and phase 5's `_twin_row`. Phase 3's `from_measurement` would have written 0 into a CHECK requiring NULL | 2, 3, 4, 5 | Phase 2 is the source of truth (D11). Phase 3: `beaten INTEGER NOT NULL`, CHECKs and `insert_yardstick` mirror `__post_init__` (NA: `draws=0, beaten=0, percentile, ratios NULL`; measured/unmatched: `draws>=1`, percentile set); `YardstickRow.beaten: int`; new test `test_from_measurement_takes_every_shape_the_engine_returns`. Phase 4: `_reading`, `stamp_yardstick`, the `_blocking` test dict use `beaten=0`. Phase 5: `_twin_row(..., beaten=0)`; the snapshot publishes `beaten: null` for NA, so the web contract is unchanged |
| Contract drift: phase 3 left `unmatched` unconstrained and assumed `rates` may hold None in draw order; phase 2 gives unmatched a percentile and `rates` as sorted floats | 2, 3 | Phase 3's CHECK and `insert_yardstick` now require `draws>=1` and a percentile for every non-NA status; `rates_json` documented as sorted floats; `_yardstick_line` keys its "-" on `draws` instead of `beaten is None` |
| Gap: a bracket (`DESIGN_V0`) arm reads not-applicable and is never re-run, so R1.6 cannot fire for it | 2, 3 | Phase 3 records it `not-applicable` with `reproduced` NULL, says so in `_yardstick`'s docstring and the table comment, and tests it (`test_a_not_applicable_arm_on_its_recording_store_is_recorded_with_reproduced_null`, added to P3.J4). Decision D12 |
| Duplicate work: phase 4 `runner._yardstick_row` vs phase 3 `YardstickRow.from_measurement` | 3, 4 | Phase 4's dropped; `trial_rows` calls `from_measurement(reading, trial_n=0, ..., checked=True)`; `runner` no longer imports `json` |
| Duplicate work: phase 4 `_job_count` vs phase 3 `_positive_count` | 3, 4 | Phase 4's dropped; `lab run --jobs` uses `type=_positive_count` |
| Duplicate work and broken build: two functions named `_yardstick_line` in `commands/lab.py` (phase 3's table row, phase 4's sentence) — a redefinition (ruff F811) | 3, 4 | Phase 4's dropped; `_run` logs `_yardstick_line(r.trial.candidate_id, r.yardstick, "")`; phase 3's docstring names `lab run` as a second caller |
| Duplicate check: `labkit.stamp_yardstick` | 3, 4 | Phase 3 has no fixture helper (its tests build rows locally), so it stays in phase 4 as the one |
| Unmet assumption: phase 4 calls `store.yardstick_clears` on a `sqlite3.Row`, a dict and `dataclasses.asdict(YardstickRow)` | 3, 4 | Phase 3's contract, docstring and a new test (`test_yardstick_clears_reads_a_row_a_dict_and_a_dataclass_alike`) state and prove any mapping |
| Gap: `prereg.gate_text` (the gate a pre-registration records) did not name the yardstick | 4 | Phase 4 Step 16b adds the clause and a test. No test pins the historical text of an already-written pre-registration (`parse` reads `gate:` freely; the tests check membership and `startswith`), so only newly written files carry it; committed files are frozen. Decision D13 |
| Gap: `RedonePanel` prints raw `failedNow` labels, so the owner would read `not a control arm` / `beats 90% of random twins` | 5 | Phase 5 adds `view.missInWords` (the two new labels in plain words, every older label unchanged), uses it in `RedonePanel`, and tests it (P5.J6). Decision D15 |
| Gap: skill text that lists the dev screen's conditions had no owner beyond two named skills | 4, 5 | Phase 4 owns all of it: Step 19d is a grep over the skills, runbooks and `CLAUDE.md` with the expected hits listed (explore SKILL.md:383, update-stale skill's constants list) and what to leave (§1 conditions, buy conditions, "all six variants", `workedSummary`'s six sentences). Phase 5 touches no skill but `sera.md` |
| Ordering ambiguity: phase 4's reading of the `lab reevaluate` door | 4 | Accepted as written: staged exactly as `verdict` (a failing reading always blocks; a missing reading blocks only arms run on or after `YARDSTICK_SINCE`); only `lab promote` refuses unmeasured arms of any age. Matches Decision D5 |
| File collision: later phases quoted pre-change state with "if phase N placed X there" in `store.py` (`_SCHEMA`, constants, helpers section, module docstring, `verdict` body, `Verdict` docstring), `runner.py` (imports, `Ran`, item 4, the `trial_rows` loop and `Ran(...)` call, the `run_method` inserts), `commands/lab.py` (`_HANDLERS`, subparsers, docstring) and `lab-cli.md` | 3, 4 | Every conditional anchor rewritten to quote the file as the earlier phase leaves it: phase 3 inserts after `CONTROL_LABEL`, `_ROLES_TRIGGERS`, `{_ROLES_TRIGGERS[1]};`, `unroled_dev_trials`, the `trial_roles` bullet; phase 4 after phase 3's `YARDSTICK_LABEL`, after phase 1's control block in `verdict`, phase 1's rewritten `Verdict` paragraph, `Ran.role`, phase 1's `insert_roles` block, and a merged item-4 docstring. `lab-cli.md`: phase 3 appends after phase 1's `reevaluate --demote` clause and gotcha; phase 4 brackets phase 3's drive lines with two `lab status` lines and appends after phase 3's gotcha |
| Label order across phases | 1, 4, 5 | Confirmed and stated in phases 1, 4 and the index: owner conditions, luck label, `CONTROL_LABEL` (phase 1), `YARDSTICK_LABEL` (phase 4), in `verdict` and in `trial_rows` |
| Broken-build risk: hardgate D20 runs before D19/D16/D17/kin, so fixtures expecting a later refusal or a pass need a clearing reading | 1, 3, 4 | Phase 4 already stamps `test_lab_hardgate.py`, `test_lab_prereg.py`, `test_lab_status.py`. Checked every test file: `test_lab_fold_verdict.py`'s one `check` is refused earlier (fold majority) and needs none; `test_lab_test_window.py` only builds an argv; phases 1 and 3 add no file that promotes. Stated in phase 4; its Steps 10-16b test run now includes those files |
| Web label pin: `web/lib/sera/lab.test.ts:56-70` fails once `lab.json` carries a new label | 5, index | Phase 5 teaches the web both labels; P5.J1 now also asserts the export of the unmodified committed `lab/lab.sqlite` carries neither. One-line note in Invariant 2 |
| Gap in every plan: no commit step naming paths; phase 5's Build used `engine/.venv` without creating it | 1-5 | Each plan gained a **Commit** block with explicit paths and a `lab/lab.sqlite` restore/check (invariant 2); phase 5's Build creates the worktree venv like phases 1-4 |
| Unreproducible proof input: phase 4's Step 17 and P4.J4 ran a script from the planning session's scratchpad | 4 | Script inlined into Step 17 (saved to `$TMPDIR` by the phase session, never committed) and extended with the yardstick-label count P4.J4 needs; the figures it produced are labelled unverified until re-run |
| Round 2 — broken test against the round-1 contract: phase 4's `test_a_test_window_row_never_reads_the_yardstick` called `stamp_yardstick` on a `window="test"` trial, which phase 3's `insert_yardstick` refuses with `LabError` ("not a dev arm"), so the test would have errored instead of asserting | 3, 4 | Phase 4's test no longer stamps the look: it asserts `yardstick_of` is None for a test row recorded on `YARDSTICK_SINCE` and that `published_verdict` adds no label (the state that fails a dev arm closed). Test name and P4.J3's `15 passed` count unchanged; phase 3's `test_insert_refuses_a_test_window_look` still proves the refusal |
| Round 2 — contract drift in prose: phase 4's runbook said `lab yardstick` "refuses a store whose prices are not the ones the arm was recorded on"; phase 3 measures on any dev store and records `reproduced` NULL off the recording store, refusing only an arm that does not reproduce on its own store | 3, 4 | Runbook sentence rewritten to phase 3's behaviour. Round-2 walk otherwise clean: every call in phases 3-5 to `role_of_trial`, `RoleRow`, `insert_roles`, `CONTROL_LABEL`/`CONTROL_ROLE`, `demote_method`, `yardstick.measure`/`Measurement`/`STATUS_*`/`Unreproducible`/`RULE_ID`/`DRAWS`, `YardstickRow`/`from_measurement`, `insert_yardstick`, `has_yardstick`, `yardstick_of`, `yardstick_clears`, `yardstick_due`, `YARDSTICK_LABEL`/`_MIN_PERCENTILE`, `_positive_count`, `_yardstick_line`, `stamp_yardstick` matches its defining phase in name, argument order and return shape; every fixture and proof row (phase 3 `_row`/stand-ins, phase 4 `_reading`/`stamp_yardstick`, phase 5 `_twin_row`/J2/J4) satisfies the D11 CHECKs; quoted "before" snippets for `store.py`, `runner.py`, `commands/lab.py`, `prereg.py` and `lab-cli.md` match the file as the previous phase leaves it; `lab/yardstick.py` imports neither `runner` nor `store` (its `lab.method`/`control_shape`/`backtest.dev` imports reach neither); phases 1-3 tests use nothing from a later phase, and phase 1's run tests stay green after phase 4 (their TIMING-on-SPY arms read not-applicable, which clears) |
| Consequence of a fixed `YARDSTICK_SINCE`: trials recorded on `main` by pre-merge code on or after 2026-11-14 have no reading and so fail closed once the set lands | 4, 5 | Kept (D14). They fail only when every other condition passes, `lab yardstick --pending` picks them up (`yardstick_due` accepts a yardstick-only failure), and P4.J4 reports the count instead of failing on it. The integrator's regenerated `lab.json` may therefore carry `beats 90% of random twins`, which phase 5's web reads |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| D1. "per setup … cache the distribution" vs the code having no machine-readable setup | per arm: twins replay that arm's own recorded decisions, cached per (trial, rule, store) in `trial_yardstick` | 6: surrounding convention — every allocator is bespoke; replay reproduced `M0562-W60-B100` exactly (measured) |
| D2. "in place of today's 'beats SPY and clears the luck score'" vs keeping them | the yardstick is added as a seventh condition; nothing is removed | 1: invariant 7 — and on the merits: a percentile among twins does not correct for 415 tries, which is the deflated Sharpe's job |
| D3. schema version bump vs additive tables | additive tables, `SCHEMA_VERSION` stays `"8"` | 1: invariant 3 |
| D4. re-judge the recorded arms inside the plan set vs after it lands | after: a runbook and `lab yardstick --pending`, run on `main` | 1: invariant 2 |
| D5. old arms with no yardstick row: fail closed at once vs staged | staged: the condition binds an old arm once it is measured, binds every arm run on or after `YARDSTICK_SINCE`, and `lab promote` fails closed for all | 1: invariant 5 |
| D6. demotion on every `lab reevaluate` sweep vs an explicit flag | explicit `--demote` | 6: surrounding convention — `reevaluate_method` is "deliberately narrow" |
| D7. the yardstick statistic | the funded rate `make_row` ranks on (money-weighted return, else CAGR); ties count against the arm | 6: surrounding convention |
| D8. how a twin name is drawn | an index member within ±25 ranks of the real pick by 63-bar median dollar volume, never a name the twin book holds or the arm itself picks at that decision, fixed for the whole holding spell (spells tracked over rank decisions only; a resize-only decision is copied unchanged, `Decision.rank`), redrawn only when it stops trading | 4: the Why — "pool, book size, cadence, weighting" must match, and trading size is the pool property every book shares |
| D9. draws and bar | 200 draws, bar 0.90, neither a CLI flag | 5: raw input — "a few hundred", "roughly the top tenth" |
| D10. demotion one-way (as planned) vs reversible | reversible: plain `lab reevaluate` also unblocks a demoted method's recorded-eligible arm that clears every condition today; phase 1 owns it | 2: phase exit criteria — the door must be reversible, and the Rollback promises it |
| D11. shape of a not-applicable / unmatched reading: phase 2's `Measurement` (NA `beaten = 0`; unmatched carries a percentile) vs phase 3's table (NA `beaten` NULL; unmatched unconstrained) and phases 4-5's fixtures (`beaten=None`) | phase 2's `Measurement.__post_init__` is the source of truth; the table, `insert_yardstick`, `from_measurement`, every fixture and the snapshot test mirror it; the snapshot publishes NA `beaten` as null so the web contract stands | 3: the plans' code blocks — phase 2's constructor is the code that produces every reading |
| D12. bracket (`DESIGN_V0`) arm under R1.6: a refusal of its own vs record it | recorded `not-applicable` with `reproduced` NULL and exit 0; nothing to reproduce, nothing to refuse | 3: the plans' code blocks — phase 2's `measure` never re-runs a bracket arm and returns `reproduced=None`; index Scope already says they read not-applicable |
| D13. `prereg.gate_text` unchanged vs naming the yardstick | names it, built from `YARDSTICK_LABEL` / `YARDSTICK_MIN_PERCENTILE`; only newly written pre-registrations carry it, committed files stay frozen | 6: surrounding convention — `gate_text` is built from the constants that decide, "so a file cannot claim a condition the code stopped applying" (or omit one it applies) |
| D14. `YARDSTICK_SINCE` fixed at 2026-11-14 vs the merge date | fixed; arms recorded on `main` after it by pre-merge code fail closed until `lab yardstick --pending` measures them | 3: the plans' code blocks — phase 4's constant and its test pin the date; D5's staging still covers every arm recorded before it |
| D15. `RedonePanel` printing raw `failedNow` vs plain words | phase 5 maps the two new labels to plain words there; older labels left as they are | 1: invariant 8 — text the owner reads carries no ids, digests or code |

## Open Questions

None.

## Rollback

- **Per phase:** each phase is one or more commits on `feature/random-twin-yardstick`; `git revert`
  them in reverse order. Phases 1-4 add tables with `IF NOT EXISTS` and never bump the schema
  version, so reverted code still opens a database that holds the new tables.
- **Whole set, before the backfill:** revert the merge. The new tables stay in `lab/lab.sqlite`,
  empty and unread.
- **Whole set, after the backfill:** revert the merge. The role and yardstick rows stay (they are
  append-only) and nothing reads them. Methods moved by `--demote` read `rejected`; plain
  `lab reevaluate` moves back any that clear today's bars.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f .workflows/plan/RANDOM_TWIN_YARDSTICK_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f .workflows/plan/RANDOM_TWIN_YARDSTICK_PLAN.md

After the set lands on `main`, re-judge what the lab already holds, following
`docs/runbooks/yardstick-backfill.md` (written by phase 4). It is three lab commands and a stage:

    engine/.venv/bin/python -m seer_engine lab roles --backfill

    engine/.venv/bin/python -m seer_engine lab yardstick --pending --jobs 2

    engine/.venv/bin/python -m seer_engine lab reevaluate --demote

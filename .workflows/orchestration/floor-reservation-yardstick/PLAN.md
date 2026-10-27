# Plan: the three unlanded items from sera-20261026-1320

**Slug:** floor-reservation-yardstick
**Date:** 2026-10-27 08:26:13
**Analysis:** `docs/analyzer/20261027-082613-F3K9_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/floor-reservation-yardstick`
**Branch:** `feature/floor-reservation-yardstick` (base: `origin/main` @ `35b41bd`)
**Phases:** 3
**Status:** landed (merged to main at d942857)
**Coordinator:** orch-floor-reservation-yardstick

---

## Why

The user's rationale, verbatim:

```
docs/plans/2026-10-27-sera-20261026-1320-handover.md

This handover is from the Sera coordinator session that just finished. Read it in full first; it
carries the leftover tasks, the open decision, and a list of traps that cost the previous session
real time.

Priorities as the handover states them, highest value first:
1. The printed-price floor repair, six code sites, measured and unlanded. The handover names all
   six and the three modules that merely delegate.
2. The order-reservation bug, which silently makes any unequal-weight book skip some of its own
   picks.
3. M0396, retrofitting the never-step-aside arm by amendment to the thirteen timing methods
   lacking one. No method id and no test look.

Do NOT act on the M0392 roster question. It was cancelled deliberately and the handover explains
why it must stay cancelled.

Two standing constraints from CLAUDE.md that bind you: never commit lab/lab.sqlite or
web/data/lab.json outside of `lab stage`, and commit explicit file paths only, never
`git commit -a`, because other sessions share this checkout.
```

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Land the printed-price floor repair at the six sites the handover names, and account for the three delegating modules | 1 |
| R2 | Fix the order-reservation bug that silently makes an unequal-weight book skip its own picks | 2 |
| R3 | M0396 — retrofit the never-step-aside arm by amendment to the timing methods lacking one. **Thirteen by the handover's `max(trials.exposure) < 0.98` read; ten in fact** — `M0173`, `M0336` and `M0338` already carry the arm. No method id, no test look | 3 |

**R3's count, corrected.** The handover's census used `max(trials.exposure) < 0.98`. `exposure` is
`mean(invested / equity)`, so a long-only stock book that never steps aside still reads about 0.97
because it always carries residual cash: the cutoff detects a SPY-at-full-weight chassis and
nothing else. Three of the thirteen already carry an explicit never-step-aside arm, confirmed in
both the lab database and the method files and re-measured against
`file:/home/miftah/seer/lab/lab.sqlite?mode=ro` on 2026-10-27:

| candidate | rationale, verbatim from its method file | trades | turnover | exposure | maxDD |
|---|---|---|---|---|---|
| `M0173-EXP100` | "Control: the dividend book never stepping aside for the curve watch" | 576 | 4.2962 | 0.9746 | 0.5765 |
| `M0336-NEVER` | "Control: the dividend book never stepping aside for the curve" | 576 | 4.2962 | 0.9746 | 0.5765 |
| `M0338-NOSW` | "no opinion: same book, switch off, always invested" | 1474 | 7.3482 | 0.9713 | 0.6087 |

`M0038-DIV-OPEN`, `M0173-EXP100` and `M0336-NEVER` are the identical book to every recorded digit
— 576 trades, turnover 4.296218435760635, exposure 0.9745847525069085, max_drawdown
0.5764932745904585 — reached through three different allocator ids and run on two dates eight days
apart. So **R3 is ten `Amendment` blocks: M0038, M0039, M0113, M0136, M0167, M0245, M0260, M0261,
M0262, M0334.** M0038 is in the ten on its `spy` half only; its `div` half's yardstick is already
`M0038-DIV-OPEN`. The thirteen figure is recorded beside the ten rather than deleted, because it is
what the handover and every artifact built from it say.

## Scope

**In scope**

- A shared, supported, tested printed-price floor helper, and the printed basis made reachable
  from the two editable screens (`f_factor`, `f_fundamental`) through **function arguments**, never
  a dataclass field.
- The `sim/book.py` buy-budget accounting repair, arriving as a `TradeRules` lever whose default is
  today's behaviour.
- **Ten** committed `Amendment` blocks pre-registering one never-step-aside arm each (thirteen by
  the `exposure >= 0.98` read, ten in fact — see the Requirements note), plus the runbook for
  executing them later and the recorded census correction.

**Out of scope, and why**

- **The M0392 roster question.** Cancelled deliberately by the owner; the handover explains why it
  must stay cancelled. No phase touches `paper/roster.py` or `db/migrations/`.
- **Editing any lab method file's existing content.** `m0052`, `m0109`, `m0117`, `m0276`, `m0383`
  and `m0387` are committed pre-registrations with recorded `source_sha`; see Decisions D1.
- **Amending `m0173`, `m0336` or `m0338`.** They already carry the arm, and a second registration
  of the same configuration would be refused by `store.has_trial`. Recorded as a measured finding,
  not an omission; see Decisions D7.
- **Running `lab run --amend`.** Phase 3 pre-registers; it does not execute. See Decisions D6.
- **Share counts on the paper night** (insights 778/779: table + migration + loader + nightly job).
  Recorded as the standing blocker on the printed floor ever running live; not built here.
- **Promoting any repaired book to the roster.** No new `PRESETS` entry is added (Decisions D5).

## Invariants

1. **The tree builds and the engine suite passes at the end of every phase**, run from the
   worktree with `PYTHONPATH=engine/src` and `PG_TEST_URL` exported.
2. **No recorded lab state moves.** `trials.config_digest`, `methods.source_sha`,
   `method_amendments`, `tests/test_registry.py`'s pinned candidate digests and the live paper
   `strategies.params` spec digests are all byte-identical before and after this plan set. Every
   phase proves its own half of this.
3. **`lab/lab.sqlite` and `web/data/lab.json` are never committed outside `lab stage`.** No phase
   in this set runs `lab stage`, and therefore no phase commits either file. If a lab command is
   run for a read, open the DB `file:lab/lab.sqlite?mode=ro` so the connect-time migration cannot
   dirty it, and restore the file by path if it moves.
4. **Every commit names explicit file paths. Never `git commit -a`, never a broad pathspec.** Other
   sessions share this checkout.
5. **No lab method file's existing content is edited.** Phase 3 appends an `Amendment` block and
   the two lines the `Amendment` mechanism requires above it (the `Method` import, and one
   `amendments=(...)` line inside the `Method(...)` call), and changes nothing else.
6. **No phase reads the test window**, spends a test look, or touches `engine/.research-test`.
7. Module docstrings explain *why* the code is shaped the way it is, matching the surrounding
   style. `%` stays escaped as `%%` in argparse help.
8. **`factor_rows`'s default stays `price_basis="adjusted"`, in every phase, and `FactorParams`
   gains no field.** *(Cross-phase: phase 1 guarantees it, phase 3 depends on it.)* Phase 3's ten
   arms are retrofits — an `Amendment` asks one more question of an idea under the same conditions
   as its recorded arms — and four of them (`M0260-ALWAYS`, `M0261-ALWAYS`, `M0262-ALWAYS`,
   `M0334-ALWAYS`) reach `factor_rows`. If phase 1 ever moved the default, the pool would shift
   under them and **phase 3's whole retrofit would be void**: its new arms would be scored on a
   different universe from the arms they exist to be subtracted from. Phase 3 raised this as a risk
   against phase 1 and phase 1's Interface Contract is exactly the guarantee that answers it, so it
   is stated here as a plan-set invariant rather than left as one phase's worry. Both plan files
   cross-reference it. A later session that changes that default must re-plan R3 in the same
   breath.
9. **No params dataclass may gain a field, in any phase — `TradeRules` is the sole exception.**
   `backtest/registry.py:323` applies the pinned-default drop-out to `TradeRules` **only**, so a
   new `compare=True` field on any *allocator* params dataclass moves every recorded
   `config_digest` that embeds it. Phases 1 and 3 discovered this independently and both avoid it:
   phase 1 threads a keyword argument, phase 3 gives each new allocator its own fresh
   `AlwaysParams`. Phase 2 appends a field to `TradeRules`, which is legal only because of that
   carve-out and only while `reserve_basis` sits in `LEVERS_SINCE_PINS` at its pinned no-op default
   `"order"`. Stated once here; cross-referenced in all three plan files.

## Environment

Measured on this machine 2026-10-27. These supersede what `CLAUDE.md` and the phase-plan drafts
say, and every plan file has been corrected to match.

| | what is written | what is here |
|---|---|---|
| interpreter | `CLAUDE.md`: `python3.11 -m venv engine/.venv` | **`python3.11` does not exist.** `python3` is CPython **3.12.7** from `/home/miftah/miniconda3/bin`; the main checkout's venv is 3.12.7 |
| worktree venv | phase 1's draft risk: `engine/.venv` is empty, `import numpy` fails | **built and working** — 3.12.7, numpy 2.5.4, pytest 9.1.1, `import seer_engine` ok. The draft was true when it looked; the venv has since been rebuilt, so the risk is **retired** |
| Postgres | `CLAUDE.md` exports `PG_TEST_URL` in the DB-test recipe | **not exported by default**, and the `seer-pg` container had been stopped for 26 hours. Restarted. CI fails if the DB tests skip, so a silent local skip is a failure that reaches CI |

Every phase's test commands therefore begin:

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
engine/.venv/bin/python -c "import numpy, pytest, seer_engine; print('venv ok')" \
  || (python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]')
docker start seer-pg 2>/dev/null \
  || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
docker ps --filter name=seer-pg --format '{{.Names}} {{.Status}}'   # must print "seer-pg Up ..."
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
```

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | The printed-price floor, landed where it legally can be | R1 | `engine/src/seer_engine/strategies` | 5 | — | NORMAL | `.workflows/plan/floor-reservation-yardstick/phase-1.md` | P1-ENG-AMD0 | — |
| 2 | The order-reservation repair, as a pinned-default lever | R2 | `engine/src/seer_engine/sim` | 7 | — | HARD | `.workflows/plan/floor-reservation-yardstick/phase-2.md` | P1-ENG-BL71 | — |
| 3 | M0396 — ten never-step-aside arms, pre-registered | R3 | `engine/src/seer_engine/lab/methods` | 11 | — | HARD | `.workflows/plan/floor-reservation-yardstick/phase-3.md` | P2-ENG-9UT4 | — |

The three phases share no file and no symbol. They may run concurrently. The only cross-phase
coupling is a *non-change*: invariant 8, which phase 1 must not break and phase 3 relies on.

### Phase 1 — The printed-price floor, landed where it legally can be
**Satisfies:** R1
**Owns:** a new `engine/src/seer_engine/strategies/price_floor.py` holding the canonical printed
close and the three-rung floor dial; a keyword-only basis argument (default = today's adjusted
behaviour) threaded into `f_factor._eligible_mask`/`factor_rows` and `f_fundamental`'s `:403`
comparison; a new `engine/tests/test_price_floor.py`; one documentation note
(`docs/lab/price-floor.md`) recording sites 3-6 as frozen with the legal route to repairing them.
**Does not touch:** any file under `lab/methods/` (the new test module *imports from* `m0383` and
`m0387`; importing is not editing — D8); `FactorParams` / `FundamentalParams` field lists;
`strategies/__init__.py`; `sim/`; `paper/`; `web/`.
**Exit criteria:** the printed basis is reachable and tested from both shared screens; the five
real-world closes M0383 verified are pinned without reading any research store; every default-path
call produces byte-identical behaviour (`plain == explicit == with_market`) and every pinned
candidate digest in `tests/test_registry.py` is unchanged; the standalone re-digest reports
`drifted: 0` with `lab/lab.sqlite`'s md5 unchanged; the three delegating modules are shown to need
no change; `ruff check engine` is clean and the engine suite is green with `PG_TEST_URL` exported.

### Phase 2 — The order-reservation repair, as a pinned-default lever
**Satisfies:** R2
**Owns:** one appended `TradeRules` field (`reserve_basis`) with its `Literal`, `_RESERVE_BASES`,
validation, docstring paragraph, `_V0_LEVERS` element, `LEVERS_SINCE_PINS` entry and conditional
`describe_rules` line; the `step_book` buy-loop accounting at `sim/book.py:776`/`:795` and its
step-4 docstring; the pinned lever table in `tests/test_sim_rules.py:429`; the pinned full
`TradeRules(...)` literal in `tests/test_backtest_dev_report.py:569-574`; the regression and no-op
proofs appended to `tests/test_sim_book.py`; a new `tests/test_reserve_basis_pins.py`; and the
generated golden fixture `tests/fixtures/sim_book_reserve_order_golden.txt`.
**Does not touch:** `PRESETS` (no new preset — D5); `sim/sizing.py` (the bracket engine is a
separate, genuinely night-before path with no leak to repair); `strategies/`; `lab/methods/`;
`paper/`; `web/`.
**Exit criteria:** a test reproduces an unequal-weight book declining a pick it chose at the
default and buying it under the lever, and the `no_bar` and cash-clamp leaks each have a test that
fails at `"order"` and passes at `"fill"`; the golden ledger was captured from the **pre-change**
engine (Step 0 before Step 2) and the default basis replays it while the fill basis demonstrably
does not; `"reserve_basis"` appears in no `candidate_text`, no `config_text` and no
`roster.rules_dict` for any registry candidate, lab variant or preset; both §5 parity tests pass
untouched; the engine suite is green with `PG_TEST_URL` exported.

### Phase 3 — M0396: ten never-step-aside arms, pre-registered
**Satisfies:** R3
**Owns:** exactly one appended `Amendment` block in each of `m0038`, `m0039`, `m0113`, `m0136`,
`m0167`, `m0245`, `m0260`, `m0261`, `m0262`, `m0334`, together with the two lines the mechanism
requires above it in each file (the `Amendment` import and one `amendments=(...)` line inside the
`Method(...)` call); nine new per-method `*-ALWAYS` allocators with their own `AlwaysParams`
(M0334 needs none — its own `Params(flat=100)` dial already expresses the arm); one runbook,
`docs/runbooks/2026-10-27-m0396-never-step-aside-retrofit.md`, naming the **ten**
`lab run --amend` invocations, their environment, and the corrected census.
**Does not touch:** anything else above the appended block in any method file; `m0173`, `m0336`,
`m0338` (they already carry the arm — D7); `lab/lab.sqlite`; `web/data/lab.json`; `strategies/`;
`sim/`; any method outside the ten.
**Exit criteria:** ten pending amendments, each declaring one arm of that method's own chassis that
never steps aside, pinned to that method's own lookback so the yardstick opens on the same session
its gated arms did; `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` green via
`runner.pending_amendment` for all ten;
`test_every_recorded_configuration_still_digests_to_its_recorded_digest` green;
`test_allocator_ids_are_unique_across_methods` green; `tests/test_lab_methods.py` smoke-runs all
ten new candidates through `dev.run_candidate`; the runbook exists and records why `m0173`,
`m0336` and `m0338` are absent; **no lab run is executed and no lab state is written**.

## Reconciliation Log

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | The index, the analysis and phase 3's framing said R3 covers **thirteen** methods; phase 3's own re-measured census said **ten** | Contract drift (a plan's stated scope against its own implementation steps) | Resolved to **ten**, measured against the lab DB this session (D7). Corrected in the index (R3 row, Requirements note, Scope, phase-3 row title / Files / Owns / Exit criteria), in the analysis (§R3, the R3 reference-list table, impact points 10-11, the Requirement IDs table footnote) and in phases 1, 2 and 3. The superseded figure is recorded beside the corrected one everywhere, with the reason the `exposure >= 0.98` cutoff is the wrong detector — never silently deleted |
| 2 | Phase 1's Handoffs said phase 3's arms reach `factor_rows` in **five** cases including `M0338` | Gap created by #1 | Corrected to **four** (M0260, M0261, M0262, M0334). M0338 reaches `factor_rows` but is one of the three methods phase 3 does not amend; phase 1 now says so |
| 3 | Phase 1 and phase 2 each referred to phase 3's "thirteen pending amendments" when telling a session not to misread a red `test_lab_methods.py` | Gap created by #1 | Both corrected to ten |
| 4 | The index gave phase 2 **4** files; phase 2's own Files table lists **7** (two discovered: `tests/test_backtest_dev_report.py`, which pins the full `TradeRules(...)` literal, and the generated golden fixture) | Contract drift | Index corrected to 7. Both extras are genuinely phase 2's: the dev-report test moves the moment a `TradeRules` field is appended, and the fixture exists only because the no-op proof demanded a pin of the pre-change engine |
| 5 | The index gave phase 3 **14** files; phase 3's Files table lists **11** after the census correction | Contract drift | Index corrected to 11 (ten method files + one runbook) |
| 6 | Phase 3 carried "if phase 1's default ever moves, this retrofit is void" as a one-sided risk against a phase that could not see it | Unmet assumption | Promoted to **plan-set invariant 8**. Phase 1's Interface Contract now states it as a guarantee it owes phase 3; phase 3's Handoffs now points at the invariant rather than at a hope. Neither plan's steps changed — the guarantee was already true, it was just unstated on the owing side |
| 7 | Phases 1 and 3 independently discovered that `registry.py:323` drops pinned defaults for `TradeRules` only; phase 2 silently relies on that same carve-out | Duplicate work / unstated dependency | Stated once as **plan-set invariant 9**. All three plan files cross-reference it; phase 2's contract now names itself as the sole exception and says what makes it legal |
| 8 | All three plan files told a session to build the venv with `python3.11`, which does not exist on this machine | Broken-build step | Replaced in all three with a confirm-then-rebuild one-liner on `python3` (CPython 3.12.7), plus the measured interpreter fact. Recorded in the index's new **Environment** section and in the analysis's Dependencies section |
| 9 | Phase 1 carried a risk that the worktree venv is EMPTY and `import numpy` fails | Stale measurement | **Retired.** Re-verified: 3.12.7, numpy 2.5.4, pytest 9.1.1, `import seer_engine` ok. Replaced with the one-line rebuild command for a session that finds it broken, and the reason the old risk was true when it was written |
| 10 | Phase 1's focused-test and digest-proof commands, and phase 3's targeted-test command, did not export `PG_TEST_URL`; none of the three said to start `seer-pg` first (it had been stopped 26 hours) | Broken-build step / silent-skip | `docker start seer-pg` + a liveness check + `export PG_TEST_URL=...` added to all three plan files and stated once in the index's Environment section, with the reason: CI fails if the DB tests skip |
| 11 | Deleted-then-used, duplicate-work, file-collision, ordering and unowned-requirement checks | — | **None found.** The three phases share no file and no symbol; no phase deletes or renames anything; every `Requires (from earlier phases)` is "nothing"; all three `Depends on` are empty, so no dependency can point forward. Every impact point in the analysis is owned, and every `R` is served by exactly one phase |

## Decisions

Every fork below was settled before or during reconciliation. They are recorded so no executor
re-opens one; none is left for a phase session to decide.

| # | Fork | Chosen | Rung |
|---|---|---|---|
| D1 | Repair the four frozen method-file floor sites in place, or document them | **Document.** Sites 3-6 (`m0052:145`, `m0109:213`, `m0117:200`, `m0276:294`) are recorded pre-registrations; `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` goes red on any byte change, and worse than red, a repair there would silently change what those methods' *recorded* arms do while their `config_digest` stayed byte-identical. `docs/lab/price-floor.md` names them and the one legal route | 1: plan invariant (tests green at each phase) |
| D2 | Make the printed basis the default of the shared screens, or an option | **An option**; the default stays `"adjusted"`. Moving the pool under `factor_rows` — reached by 186 of 243 method files, called directly by 119 — would make every future amendment arm incomparable with the arms it is written to measure, and **phase 3 is exactly such a retrofit**. This is plan-set invariant 8 | 1: plan invariant (no recorded state moves) |
| D3 | Carry the basis as a params field, or a keyword argument | **Keyword argument.** `registry._canon` enumerates every `compare=True` dataclass field and drops pinned defaults for `TradeRules` only (`registry.py:323`), so a `FactorParams` field would move every recorded `config_digest` that embeds one. An argument is invisible to `_canon`. Generalised to plan-set invariant 9 | 6: surrounding convention, measured |
| D4 | Repair `step_book`'s budget unconditionally, or behind a lever | **Behind a `TradeRules` lever at a pinned no-op default** (`reserve_basis="order"`). `step_book` drives the live paper roster, and five levers precede it in `LEVERS_SINCE_PINS` doing exactly this. A golden ledger captured from the pre-change engine pins the default branch | 6: surrounding convention |
| D5 | Add a `PRESETS` entry for the repaired reservation basis | **No.** A method declares its own rule set in its own file (M0127's `T00` precedent). Promotion to paper is a later, separate step, and `tests/test_sim_rules_fixed_tape.py:74` pins `len(PRESETS) == 20` | 5: the user's raw input (smallest change) |
| D6 | Phase 3 runs `lab run --amend`, or stops at pre-registration | **Stops at pre-registration + runbook.** The runs write the shared committed `lab.sqlite`, a concurrent `lab run` can silently lose trials, and the tree is green with pending amendments by `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`'s own documented window. The runbook hands the ten commands to a later deliberate session | 5: the user's raw input (never commit `lab.sqlite` outside `lab stage`) |
| D7 | Retrofit thirteen methods, or ten | **Ten.** `M0173-EXP100`, `M0336-NEVER` and `M0338-NOSW` already carry the arm, and the `exposure >= 0.98` cutoff is the wrong detector because `exposure` is `mean(invested/equity)` and a long-only stock book that never steps aside still reads ~0.97. A second registration of the same configuration would be refused by `store.has_trial` anyway | 1: measured against the lab DB this session |
| D8 | Phase 1's test module imports `printed_close` from `m0383` and `passes_floor` from `m0387` — frozen pre-registrations — or reimplements the expected values by hand | **Import them**, and assert agreement. Invariant 5 forbids *editing* a method file; importing one does not change a byte, and `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` hashes the file, not its import count. The agreement test is the only thing that stops the supported copy drifting away from the frozen one, which is the whole reason the module exists | 2: the phase's exit criteria (the frozen copies cannot drift) |
| D9 | Phase 3's new arms run through `f_index.TIMING` with `rule="always"`, or through a new per-method allocator | **A new per-method allocator.** `TimingAllocator.lookback` returns 1 for `rule="always"`, so on M0113, M0136, M0167 and M0245 the yardstick's dev window would open eleven to sixteen months before the arms it prices (1993-02-01 against 1994-01-28 / 1994-05-17), and a bill read across a window mismatch is not a bill. It is also *one* configuration shared by six methods, so `store.has_trial` would refuse the second registration. A per-method allocator pins the method's own lookback and makes the id unique | 3: the plans' code blocks, checked against `f_index.py:286-292` and `backtest/dev.py:293` |
| D10 | M0038 is skipped (its `exposure` reads 0.9746, and `M0038-DIV-OPEN` exists), or amended | **Amended, on its `spy` half only.** `M0038-DIV-OPEN` is the yardstick for M0038's, M0039's and M0167's `div` arms — all three run the same `div` host, which is why only one of them can register it — but M0038's `spy` half has no never-step-aside arm at all | 1: measured against the lab DB this session |
| D11 | Phase 2 owns `tests/test_backtest_dev_report.py` and the generated golden fixture, or they stay unassigned | **Phase 2 owns both.** The dev-report test pins the full `TradeRules(...)` literal and moves the moment a field is appended, which is phase 2's own act; the fixture exists only to serve phase 2's no-op proof. No other phase touches either file | 5: one owner per file region |

## Open Questions

**None.** Every fork above is one commit to overturn, so none qualifies: this section is reserved
for a fork where *every* branch is irreversible, and nothing in this plan set destroys data,
rewrites published history, or runs an unrepeatable migration — phase 3 deliberately stops short of
the one action that would (D6). Every `R` in the Requirements table is served by exactly one phase.

## Rollback

Per phase: each phase is one commit (phase 3, eleven) touching files no other phase touches, so
`git revert <sha>` backs it out cleanly. Phase 3's revert additionally removes ten pending
amendments, returning every one of those files to its recorded sha.

As a whole: delete the branch and the worktree. No lab state, no database row, no deployed page and
no paper-night behaviour is changed by any phase, so there is nothing outside git to undo.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/FLOOR_RESERVATION_YARDSTICK_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f docs/plans/FLOOR_RESERVATION_YARDSTICK_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan docs/plans/FLOOR_RESERVATION_YARDSTICK_PLAN.md

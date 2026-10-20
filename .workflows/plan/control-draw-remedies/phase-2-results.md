# Phase 2 results — The shadow rule, written beside v1

**Date:** 2026-10-20
**Verdict:** **DONE.** The v2 block ships, v1 is byte-for-byte intact, and the golden vector is
real — it is now the only test in the tree that goes red when the frozen path is edited.
**Plan set:** `docs/plans/CONTROL_DRAW_REMEDIES_PLAN.md`, phase 2 of 6 (`P1-ROOT-X4PN`)
**Environment:** `main` @ `28f783d`, main checkout, no worktree, `engine/.venv` (Python 3.11).

**No trial was recorded, no method id was minted, no amendment was written, no test-window look
was spent, no method file was opened and `lab` was never invoked.** `lab/lab.sqlite` is
byte-identical before and after.

---

## 1. What shipped

`engine/src/seer_engine/lab/control_draw.py`, 308 → 607 lines, **additions only**. Two constants,
one callable type, one named tuple and five functions, appended after `matched_book`; one import
line; one docstring line replaced by the v2 section.

| Symbol | Shape |
|---|---|
| `SHADOW_RULE_ID` | `"matched-draw-v2"` — a **second** constant. `RULE_ID` is **not** bumped. |
| `FIXTURE_BARS` | `473`, asserted against `len(dates.sessions(SMOKE_FIRST, DEV_END))`, never trusted |
| `Replay` | `(date, AbstractSet[str]) -> (pool, book)` — `Select`'s sibling, one callable not two |
| `ShadowReading` | `NamedTuple(pool, real_now, real_prev)` |
| `max_shadow_depth` | `(inner) -> int` — owns the off-by-one so no method file does it by hand |
| `shadow_lookback_for` | `(inner, depth) -> int` — **raises** past `FIXTURE_BARS` |
| `shadow_decision_dates` | `(data_date, depth, cadence="monthly") -> list[date]`, oldest first |
| `shadow_selection` | `(replay, data_date, *, depth, cadence="monthly") -> ShadowReading` |
| `shadow_book` | `(replay, data_date, held, *, tag, seed, depth, cadence="monthly") -> list[str]` |

**No K is baked anywhere.** `depth` is `KEYWORD_ONLY` with `NO DEFAULT` on both entry points,
verified by `inspect.signature`; a call without one raises
`missing 1 required keyword-only argument: 'depth'`. Phase 3 ships its own number as
`SHADOW_DEPTH` in the method file.

**The contract phase 1 handed over, checked against the shipped code:**

```
M0208 inner bars (factor_lookback(m0208.N20))  : 253
v1    lookback_for(253)                        : 279
      max_shadow_depth(253)                    : 8      == phase 1's k_max
      shadow_lookback_for(253, 2)              : 305    == lookback_after[M0208], <= 473
      shadow_lookback_for(253, 9)              : raises "past the 473-bar fixture"
```

`shadow_needed = [M0208]` is consumed by phase 3, which writes the adapter; this phase writes no
method file, so the list changes nothing here beyond the no-op proof below.

---

## 2. The hazard, closed — and it is the phase's most valuable line

**The hole, re-measured on this tree before the fix.** A module body is outside `config_digest`
(`registry._canon` enumerates the rules, the allocator id and `dataclasses.fields()`), so an
in-place edit to v1 rewrites all thirteen recorded matched-draw arms (lab trials 841-853) while
every existing test stays green. Two independent perturbations were applied and reverted:

| perturbation | what it silently moves | red **without** the golden vector | red **with** it |
|---|---|---|---|
| `keep_key`: `"{tag}\|keep\|{seed}\|{symbol}"` → `…\|{symbol}\|` | the keep order of every recorded arm (`keep_key('M0208',1,'AAPL')` 11772521752773708193 → 16151905896945292564) | **0 of 46** | **1** — this one |
| `matched_names`: `sorted(book, key=(entry_key, s))` → `sorted(book)` | the fill order under a cash shortage, for nineteen years | **0 of 46** | **1** — this one |

Under **both** perturbations
`test_lab_methods.test_every_recorded_configuration_still_digests_to_its_recorded_digest`
**passed**, which is the proof the hole was real. Each run reported `1 failed, 46 passed` and the
one failure was
`test_the_shipped_draw_still_produces_the_vector_the_recorded_arms_were_drawn_from`.

**Both reverts are sha-verified.** `sha256sum control_draw.py` is
`16ff20975ad66b1a4ef1b9440bf66175b290cc69d0cd8331f56134eb6a5b1885` before each perturbation and
after each revert, and the three modules read `47 passed` again afterwards.

> **The plan's own revert command was not used, and must not be.** The phase plan's verification
> block ends with `git checkout -- engine/src/seer_engine/lab/control_draw.py`. At that point in
> the phase nothing is committed, so that command would have discarded steps 1 and 2 — the entire
> phase — and not just the perturbation. The revert was done by the exact inverse string
> replacement instead, and the sha above is how it is known to be exact. **Phase 3 and anyone
> re-running this check should do the same.**

---

## 3. The cash-month property, implemented and asserted

The coordinator's brief required this to be true of the implementation and said so explicitly.
**It is, and it falls out of the loop rather than being a case in it** — there is no cash branch
in `shadow_selection`.

```python
for i, d in enumerate(calendar):
    pool, book = replay(d, shadow)
    if i == last:
        pool_now, real_now = list(pool), list(book)
    else:
        real_prev = list(book)
        shadow = frozenset(book)        # <- an empty book makes the shadow empty
```

An empty `book` mid-chain sets `shadow = frozenset()`, so the next decision is seeded from
nothing — exactly what `book_runner` does to a real book when a target comes back empty.

**Asserted, in a test this phase added beyond the plan's twelve:**
`test_a_cash_month_in_the_middle_of_the_chain_reseeds_the_shadow_to_empty` records every
`(date, held)` the replay is called with across a chain that holds a book, goes to cash, and
comes back. It asserts the cash month is handed the previous book, that **the decision after it
is handed `frozenset()`**, and that the returning book reads `churn == len(real_now)` — the full
refill. The plan's existing `test_an_era_with_no_book_reseeds…` covers only the *leading* empty
case (a panel that has not opened), which is a different and easier shape.

**Why this matters and is not an edge case**, from phase 1's decomposition: M0208's SPY 200-day
switch holds its real book in cash for **69 of the window's 238 months**, `previous_month_end`
scores a phantom top-20 at the previous month end regardless, and on the **9 decisions following
a cash month** the shipped estimator reads **38 entries against a truth of 180 — 0.211×**. Those
nine decisions carry **44 % of M0208's whole shortfall**, against 43 % for the freshness defect
the shadow was proposed for and 13 % for the membership convention no depth closes. **So the
shadow is not only a freshness fix, and it buys the cash months for free.** Both numbers are now
written into the module docstring and into `shadow_selection`'s docstring, where the next reader
of the code will find them.

---

## 4. What is proved rather than measured

`engine/tests/test_lab_control_draw_shadow.py`, 13 tests, 469 lines. No store, no database, no
return — a calendar, the smoke fixture's eight synthetic members, two hashes and set arithmetic.

- **The calendar is the runner's own**, `depth` steps of it, exact against `is_rank_session` over
  every monthly decision of the dev window at depths 1, 2, 5 and 8.
- **v2 at `depth = 1` IS v1**, decision for decision on the banded fixture — so v2 contains v1 and
  phase 3 can argue that the only thing its arm changes is the depth.
- **The four `reads_held: false` chassis draw the identical control at every depth**, asserted
  name for name against `matched_book` itself at depths 1, 2, 5 and 8. Phase 1 *measured* M0047,
  M0221/M0225, M0227 and M0243 as no-ops (0.988–1.001); this makes the no-op **structural**, so
  nobody has to repeat that sweep.
- **The defect, reproduced**: one step sees ≤ half the banded fixture book's entries, a depth-4
  replay lands inside 0.80–1.25×.
- **Purity (invariant I9)**: the same reading in reverse order, in a shuffle, and twice over.
  This is the test that forbids the carried-state design `run_registry` would corrupt.
- **The two rule ids**: `RULE_ID == "matched-draw-v1"` still, `SHADOW_RULE_ID` beside it.

---

## 5. Verification, as run

| check | result |
|---|---|
| `ruff check engine` | **All checks passed!** |
| three control-draw modules, `-n0` | **47 passed** in 2.19s (plan predicted 46; +1 is §3's cash-month test) |
| `test_every_recorded_configuration_still_digests_to_its_recorded_digest` | **1 passed** — *and that is not evidence of anything*; it passed under both perturbations too |
| whole suite, parallel, `PG_TEST_URL` set | **6196 passed, 3 skipped** in 117.07s (plan predicted 6195) |
| the 3 skips | the pre-existing env-gated live sweeps (`test_lab_costs.py:314`, `test_lab_name_count.py:240`, `test_lab_survivorship.py:387`) — **no DB test skipped** |
| `git diff -U0` on `control_draw.py`, `-` lines | **exactly one**, the `Pure: a calendar, two hashes and set arithmetic…` docstring line |
| `git status --porcelain` | exactly the three planned paths (plus the coordinator's own `ledger.json` / `.gitignore`, not this phase's) |

**Exit criteria 1–9: all met.** Criterion 6's command as the plan wrote it —
`pytest engine/tests/test_lab_methods.py -k lookback` — **selects zero tests**; no test in that
module carries `lookback` in its name. Its substance is covered instead by the whole-suite run
(which drives the allocator contract over the fixture), by
`test_the_fixture_is_the_bars_the_lookback_ceiling_is_measured_from`, and by the live reading in
§1. **This phase adds no allocator, so no allocator's `lookback` moved at all.**

---

## 6. Invariants

| | before | after |
|---|---|---|
| `git hash-object lab/lab.sqlite` | `607b78cf69c8e4e3a68a1e84c85eedfd1040c754` | `607b78cf69c8e4e3a68a1e84c85eedfd1040c754` |
| `sha256sum lab/lab.sqlite` | `ccc5b781…2e56582e` | `ccc5b781…2e56582e` |
| test-window looks (`SELECT count(*) FROM trials WHERE window='test'`) | **4** | **4** |

- **I1** — no test-window look. `lab test` never invoked, `SEER_RESEARCH_TEST_STORE` never read.
- **I2** — nothing recorded or frozen was touched. No method file was opened.
- **I3** — v1 keeps its body byte for byte, proved two ways: the one-line `git diff -U0` audit, and
  the two perturbations of §2 that the new golden vector catches and nothing else does.
- **I4** — no `lab` command was run in this phase at all, so no exit code passed through a pipe.
- **I5** — the database was opened only through `sqlite3 "file:…?mode=ro"`. Hash unmoved.
- **I9** — no mutable allocator state: the shadow lives in a local, asserted by the purity test.

---

## 7. Decisions taken on the ladder, not asked

| fork | decided | rung |
|---|---|---|
| The plan's perturbation revert is `git checkout -- control_draw.py`, which would discard the whole uncommitted phase | revert by the exact inverse string replacement, sha-verified both times | tie-break: *take the reversible option*; and the brief's own ban on tree-wide git |
| Criterion 6's `-k lookback` selects zero tests | report the drift, cover the substance by the whole suite + the fixture test + the live reading in §1 | 2 (exit criteria) over 3 (the literal command) |
| The coordinator required the cash-month property be real "and say so" | add one test and two docstring paragraphs carrying phase 1's measured numbers, inside the file this phase owns | 5 (the brief), not conflicting with any higher rung |
| Nothing in the plan's Files table is a report, but criterion 4 says "the phase's own report" | write this file | 2 (exit criteria) |

---

## 8. Handoffs

- **Phase 3 (R1)** calls `shadow_selection(replay, data_date, depth=SHADOW_DEPTH)` and
  `shadow_lookback_for(inner, SHADOW_DEPTH)` with **no further change to `control_draw.py`** —
  verified live in §1. `SHADOW_DEPTH` is a module-level `int` in the **method** file, never a
  params field: `registry._canon` renders a dataclass by `dataclasses.fields()`, so one more field
  on `OverhangParams` would move every recorded M0208 digest.
- **Phase 3 ships its own K.** Phase 1 proposed 2 (0.989, 305 of 473 bars). The two may legitimately
  differ — phase 1's `(b) SHIPPED` column reproduces amendment 1's *unguarded* reading while phase
  3's probe closes the SPY 200-day switch inside the replay.
- **Phase 3 stamps `SHADOW_RULE_ID`**, not `RULE_ID`. Nothing in this module changes for it.
- **Phase 5 (R2)** quotes `control_draw` as it looks now and edits none of it. The v2 docstring
  states outright that the shadow never touches a weight, so `control_weight` need not argue it.
  `test_lab_control_draw_twins.py` was **not opened** by this phase.
- **The revert hazard of §2** applies to anyone re-running the perturbation check.
- **No quarterly cadence was added.** `CADENCES` is still `("monthly",)`; `shadow_lookback_for`
  and `max_shadow_depth` multiply by `PREVIOUS_DECISION_BARS` and are monthly-only by
  construction. M0201/M0202 must not call either — and per the coordinator they get no shadow at
  all, their K curve running backwards (0.966 → 0.947 → 0.946).
- **The membership convention was not attempted.** The v2 block takes no `members` argument. It is
  phase 6's leftover, priced at **0.067 of ratio on M0208** (not 0.202), ≤ 0.046 elsewhere.
- **`SMOKE_BARS = 473` is still duplicated** at `test_lab_control_draw.py:43` and
  `test_lab_control_draw_twins.py:36`. `FIXTURE_BARS` now exists and is asserted against the
  fixture's own session count, so both could point at it. Left alone: a drive-by across two files,
  one of which phase 5 owns.

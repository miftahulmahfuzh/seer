# Phase 12: The rebuilt roster: every entry pays Gotrade

**Plan set:** `GOTRADE_FEE_REBUILD_PLAN.md`
**Analysis:** `20261008-091321-H3M8_code_analyzer.md`
**Satisfies:** R1 (the rebuilt roster), and — moved here by the reconciler with the work, under index
Decision **D10** — the production call sites of **R4** (`commands/paper.py` passes each entry's own
rules, so C-GT's nights really are charged Gotrade's schedule) and of **R3** (`commands/paper.py`
credits the owner's deposits, and `paper/replay.py` replays them, so the successor entries carry the
funding plan from their first night). The *capabilities* behind R4 and R3 stay with phases 4, 6 and
7; this phase owns the wires that turn them on.
**Depends on:** Phase 3, Phase 4, Phase 6, Phase 7
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/paper`, `engine/src/seer_engine/commands` (plus `db/migrations`,
`docs/runbooks`, `.github/workflows`)

> ### Reconciled 2026-10-08 — this phase is also the wiring layer
>
> Three planners independently found that `engine/src/seer_engine/commands/paper.py` was wanted by
> phases 3, 4, 6 and 12 and given to none of them, with **phases 3 and 4 both in wave 1** — two
> concurrent sessions in one file. The index's Decision **D10** gives `commands/paper.py`,
> `paper/replay.py` and `commands/promote.py` to this phase, and the reconciler added
> `paper/store.py:1127` (`load_benchmark`) and `commands/paper_check.py:200` to the same block for
> the same reason. **Step 7 below is now Steps 7a–7e and carries every one of those edits, with the
> exact code the other phases specified.**
>
> This is safe because every signature phases 3, 4 and 6 add is **keyword-with-a-default**, so the
> tree builds and both suites pass at the end of each of them with the wiring absent — the
> capabilities are complete and *inert* until this phase turns them on, which is exactly the state
> the pause already holds the system in. This phase already depends on 3, 4, 6 and 7, so it is the
> only phase that can quote every signature as it actually landed; Step 0 reads them off the merged
> tree rather than trusting this plan's predictions.

---

## Goal

Six successor roster entries — `SPY-GT`, `C-GT`, `RMW-FR-GT`, `RAW-FR-GT`, `MOM-FR-GT`, `MVW-FR-GT` —
exist with fresh paper clocks, each paying Gotrade's measured fee schedule and each recording the
owner's funding plan in its frozen spec. The six predecessors are retired, not deleted, and not one
of their thirteen pinned digests moves. Paper stays paused; the migration lands inert, and the
resume-condition comment above `PAPER_PAUSED` now says what holds and what is left (one owner
decision). `docs/runbooks/paper-trading.md` stops stating a cron schedule that has not existed since
`d44fa78`.

This phase lands last. Phases 3, 4, 6 and 7 are already merged when it runs, so it **verifies** their
interfaces rather than assuming them — every step that touches another phase's output starts with the
grep that reads what they actually shipped.

---

## Interface Contract

**Creates:**
- `paper.roster.BENCHMARK_GT_ID` = `"SPY-GT"`, `C_GT_ID` = `"C-GT"`, `RMW_GT_ID` = `"RMW-FR-GT"`,
  `RAW_GT_ID` = `"RAW-FR-GT"`, `MOM_GT_ID` = `"MOM-FR-GT"`, `MVW_GT_ID` = `"MVW-FR-GT"`
  (`roster.py`, the id-constant block at :137-151)
- `paper.roster.BENCHMARK_SYMBOL` = `"SPY"` (`roster.py:153`) — the **symbol** the benchmark holds,
  split off from `BENCHMARK_ID`, which from now on is only the retired entry's **id**
- `paper.roster.OWNER_FUNDING: dict[str, str]` (`roster.py`, new block before `RESOLVER`)
- `paper.roster.PRE_FUNDING_IDS: frozenset[str]` (same block) — the thirteen grandfathered ids
- `paper.roster.BENCHMARK_COST_MODEL: dict[str, CostModel]` and
  `paper.roster.benchmark_cost_model(entry_id) -> CostModel` (same block)
- six `RosterRow` entries at the head of `SEED_ROWS`; four new `LAB_PROVENANCE` entries
- `db/migrations/017_roster_real_fees.sql`

**Signature changes (all in the wiring layer, all keyword-with-a-default, all added here):**
- `paper.store.load_benchmark(conn, strategy_id=BENCHMARK_ID)` ->
  `(..., *, cost_model: CostModel = "flat")` (`paper/store.py:1127`). Phase 3 specified it
  (its Handoff H1); phase 6 owns the rest of that file but is fenced off from `:1127`.
- `paper.replay.expected_bracket(market, strategy, params, head)` ->
  `(..., *, rules: TradeRules = DESIGN_V0, contributions: Sequence[tuple[date, Decimal]] = ())`
  (`paper/replay.py:280`), and `expected_book` / `expected_benchmark` gain the same
  `contributions` keyword (`:325`, `:406`). Phase 4's Handoff H1 and phase 6's Handoff 2.

  **The dated dollars, never the schedule — index Decision D18.** A replay has to reproduce the
  record a night wrote, and phase 6 freezes each deposit's rate on its landing session (its D6a)
  while a backtest converts at one rate per run (phase 5's contract point 4). Handing a runner the
  *plan* would therefore diverge from the stored record the first time the rupiah moved, and `judge`
  would report a mismatch on every session after it — the exact failure Step 7d exists to prevent.
  So all three builders take `(session, usd)` pairs straight off `store.read_contributions`, and
  phase 5's `sim.contributions.credit_for` credits them unchanged. `buy_and_hold` already takes this
  shape (phase 7), so one vocabulary reaches all three engines.

No *roster* function's parameters change.

**Behaviour changes (digest-visible):**
- `paper.roster.spec(e)` gains a conditional `"funding"` key — present for every entry whose id is
  **not** in `PRE_FUNDING_IDS`, absent for the thirteen that are. The thirteen pinned digests are
  byte-identical afterwards; this is asserted, not assumed.
- `paper.roster.spec(e)` for a `benchmark` entry now writes `"cost_rate"` only when
  `benchmark_cost_model(e.id) == "flat"`, and `"cost_model": "gotrade"` instead when it is gotrade.
  `SPY` stays `"flat"`, so `SPY`'s spec text is unchanged.

**Deletes:** nothing. No row, no file, no symbol is removed. `BENCHMARK_ID` keeps its name and value.

**Renames:** nothing.

**Requires (from earlier phases), each verified by a grep in Step 0:**
- **Phase 4** — `sim.rules` exports a bracket preset with `cost_model="gotrade"`, listed in `PRESETS`.
  This plan writes its id as the module-level constant `BRACKET_GOTRADE_RULES_ID` and assumes
  `"design-v0-gotrade"` on a non-`bracket_v0` rules engine. **If phase 4 shipped a different id, one
  string changes and the pins are recomputed** — nothing else in this plan moves.
- **Phase 4** — `paper.bracket` charges that preset's schedule, so `C-GT`'s fills are honest.
- **Phase 3** — `paper.benchmark` can charge Gotrade on all three sites and carries the model on
  `BenchmarkState` (`cost_model`, keyword-with-default `"flat"`). It deliberately wires **nothing**;
  **Step 7b of this phase supplies the model**, in `store.load_benchmark` and in
  `commands/paper.py:_step_benchmark`.
- **Phase 6** — paper can record and apply a deposit (`accrue_contributions`,
  `apply_contributions`, `read_contributions`, `paper.book.deposit_book`);
  `db/migrations/016_contributions.sql` exists, so `017` is free. It too wires nothing;
  **Step 7c of this phase calls them from the night.**
- **Phase 5** — `sim.contributions` defines the owner's schedule as a value:
  `ContributionSchedule(amount_idr, day_of_month=25)`, instance **`OWNER_MONTHLY`**, method
  **`dates_in(first, last)`**. `roster.py` imports **none** of it (that would make it an input to a
  started entry's digest); the test pins `OWNER_FUNDING` equal to it, and Step 7c reads it in
  `commands/paper.py`, which is not a digest input.
- **Phase 5** — `run_backtest(..., rules=...)` and `run_rules`'s `is_bracket` dispatch exist, which
  is what lets Step 7d replay a `"bracket"` rule set at all.
- **Phase 5** — `contributions=` on `run_backtest` / `run_book` / `run_rules` accepts a **record**
  of `(session, usd)` pairs, not only a `ContributionSchedule` (`sim.contributions.Contributions`
  and `credit_for`, assigned there by the reconciler under D18). Step 0 greps for it:
  `PYTHONPATH=engine/src python -c "from seer_engine.sim import contributions as c;
  print(hasattr(c, 'credit_for'), c.Contributions)"`. Without it Step 7d can replay the plan but not
  the record, and a replay of the plan is wrong whenever the rupiah has moved.
- **Phase 7** — `buy_and_hold(..., contributions=...)`, taking the same `(session, usd)` pairs, for
  Step 7d's benchmark replay.

**Leaves alone (owned by others):**
- `PAPER_PAUSED`'s **value** — invariant 2. Only the comment block **above** it (`:46-69`) is
  rewritten. **The `PAPER_PAUSED: 'true'` line at `:70` keeps its exact text, spelling, quoting and
  indentation**, because two other phases parse it: phase 9's drift test matches
  `/^\s*PAPER_PAUSED: '(true|false)'/m` and phase 11's watcher `sed`s
  `^[[:space:]]*PAPER_PAUSED:[[:space:]]*['"]\{0,1\}\([A-Za-z]*\)['"]\{0,1\}[[:space:]]*$`. Reformat
  that line and you turn both of them red, phase 11's by design (it exits 1 and emails the owner).
- `engine/src/seer_engine/sim/*` (phases 4, 5), `paper/benchmark.py` (3), `paper/book.py`,
  `paper/compare.py`, `db/migrations/016_*.sql` (6), `backtest/*` (5, 7), `lab/store.py` (2, 7)
- `engine/src/seer_engine/paper/store.py` **except `load_benchmark` at `:1127-1145`** — phase 6 owns
  the rest of that file (the deposit path at `:417`/`:449` and the new contributions section). The
  two regions are line-disjoint and phase 6 lands first, so this is sequential, never concurrent.
- the rest of `.github/workflows/nightly.yml` and every other workflow (11)
- all of `web/` (2, 9, 10)
- `engine/src/seer_engine/sim/costs.py` — invariant 5, never touched

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/paper/roster.py` | modify | six id constants (:137-151); `BENCHMARK_SYMBOL` (:153); `CostModel` import (:123); the funding / benchmark-cost-model block (new, before `RESOLVER` at :349); four `LAB_PROVENANCE` entries (:511); six `SEED_ROWS` rows at the head and `sort` renumbered on the thirteen below (:735-991); `spec()` (:1045-1073); module docstring (:22-26, :47-59) |
| `db/migrations/017_roster_real_fees.sql` | create | insert six rows, retire six, move the champion/benchmark flags, renumber `sort` |
| `engine/tests/test_paper_roster.py` | modify | six new pins and the thirteen unchanged ones (:85-106); `ACTIVE_IDS` / `RETIRED` / `LAB_DERIVED` / `NOT_LAB_DERIVED` (:79-80, :567-570); the two positional `SEED_ROWS[1]` lookups (:483, :489); the `promoted_from` sets (:524, :701); `test_lookbacks` (:283); three new tests |
| `docs/runbooks/paper-trading.md` | modify | the roster table (:20-37); the stale schedule line (:76); a new dated note before :288 |
| `.github/workflows/nightly.yml` | modify | the comment block at :46-69 only; `PAPER_PAUSED: 'true'` at :70 is untouched, **character for character** |
| `engine/src/seer_engine/commands/paper.py` | modify (**wiring, D10**) | Step 7a: four `rules=e.rules` (:553-555, :727-734, :777, :779). Step 7b: `_step_benchmark` passes the entry's cost model (:866-878). Step 7c: `accrue_contributions` once per entry per night, and `apply_contributions` + the engine's own deposit at the top of each of the three session loops |
| `engine/src/seer_engine/commands/promote.py` | modify (**wiring, D10**) | Step 7a: :275 dispatches on `is_bracket`; :75 import |
| `engine/src/seer_engine/paper/store.py` | modify (**wiring, D10 — `load_benchmark` ONLY**) | Step 7b: :1127-1145 gains a keyword-only `cost_model` and passes it into `BenchmarkState`. Nothing else in the file; phase 6 owns the rest |
| `engine/src/seer_engine/paper/replay.py` | modify (**wiring, D10**) | Step 7d: :290 stops hard-coding `DESIGN_V0`; the three `expected_*` builders take the stored contributions |
| `engine/src/seer_engine/commands/paper_check.py` | modify (**wiring, D10**) | Step 7d: :200's `"initial_cash"` is relabelled *capital on day 0* and `"deposited"` is published beside it |

**Ten files.** The index's draft said 5, the reconciler's first pass 8; the final figure adds
`paper/store.py` (`load_benchmark`) and `commands/paper_check.py` to the D10 block. Five of the ten
are the roster proper; five are the wiring layer, all of them additive-with-defaults and all of them
specified verbatim by phases 3, 4 and 6.

---

## Implementation Steps

### Step 0: Read what phases 3, 4 and 6 actually shipped
**File:** none — this step writes nothing.
**Change:** three facts have to be read off the merged tree before any code is written, because this
plan's defaults are predictions and the tree is the truth.
**Code:**
```bash
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild

# (a) Phase 4: the bracket Gotrade preset's id and its rules engine value.
PYTHONPATH=engine/src python - <<'PY'
from seer_engine.sim.rules import PRESETS
for r in PRESETS:
    if r.cost_model == "gotrade":
        print(f"{r.id!r:40} engine={r.engine!r} cadence={r.cadence!r} fractional={r.fractional}")
PY
# Expect three: the two book presets that already exist, plus phase 4's bracket one.
# Put phase 4's bracket preset id into BRACKET_GOTRADE_RULES_ID in Step 1.

# (b) Phase 6: 016 is taken, 017 is free.
ls db/migrations/01[5-9]*.sql

# (c) Phase 3: how the live benchmark learns its cost model.
grep -n "cost_model\|CostModel" engine/src/seer_engine/paper/benchmark.py
grep -n "load_benchmark\|step_benchmark\|BenchmarkState(" engine/src/seer_engine/commands/paper.py

# (d) Phase 5: the schedule's real names, for Steps 7c and 8. Expect OWNER_MONTHLY, amount_idr,
#     day_of_month and dates_in.
PYTHONPATH=engine/src python -c "
from seer_engine.sim import contributions as c
print([n for n in dir(c) if n.isupper()])
print(c.OWNER_MONTHLY, [m for m in dir(c.OWNER_MONTHLY) if not m.startswith('_')])"

# (e) Phase 6: the deposit path this phase calls from the night (Step 7c).
PYTHONPATH=engine/src python -c "
from seer_engine.paper import store, book
for n in ('accrue_contributions', 'apply_contributions', 'read_contributions'):
    print(n, hasattr(store, n))
print('deposit_book', hasattr(book, 'deposit_book'))"
```
**Impact:** if (a) returns only the two book presets, phase 4 did not land its preset and this phase
cannot proceed — stop and report it to the coordinator rather than inventing one. If (b) shows no
`016_*.sql`, phase 6 did not land; stop for the same reason. Same for (d) and (e): this phase is the
wiring layer, so every name it calls belongs to someone else, and **a name this plan predicted wrong
is this plan's error, not the tree's.** Correct the step and carry on; stop only when the capability
itself is missing.

---

### Step 1: The six successor ids, the benchmark symbol, and the `CostModel` import
**File:** `engine/src/seer_engine/paper/roster.py:122-154`
**Change:** add the `CostModel` import, the six successor id constants, `BRACKET_GOTRADE_RULES_ID`,
and `BENCHMARK_SYMBOL`. `BENCHMARK_ID` keeps its name and its value: it is now only the *retired*
entry's id, and `spec()` must stop using it to mean the ticker.
**Code:** replace lines 122-154 with:
```python
from seer_engine.paper.capital import PAPER_INITIAL_IDR
from seer_engine.sim import COST_RATE
from seer_engine.sim.costs import CostModel
from seer_engine.sim.rules import PRESETS, TradeRules, is_pinned_default
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import Strategy
from seer_engine.strategies.c import STRATEGY_C, STRATEGY_C_PARAMS
from seer_engine.strategies.f_factor import FACTOR
from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalParams
from seer_engine.strategies.f_index import TIMING

Engine = Literal["bracket", "book", "benchmark"]
Status = Literal["active", "retired"]
Basis = Literal["test-passed", "owner-override"]

BENCHMARK_ID = "SPY"
F4_ID = "F4-MOM12-N20-TREND"
F1_ID = "F1-SPY-SMA200-M"
FND_ID = "FND"
# The fractional-share versions (2026-10-07): the same methods under monthly-hold-frac. A changed
# rule set is a new id (frozen roster); 010 retires the whole-share F4 and F1, and FND for RM.
F4_FR_ID = "F4-MOM12-N20-TREND-FR"
F1_FR_ID = "F1-SPY-SMA200-M-FR"
RM_ID = "RM-FR"  # retired 2026-10-07 for RMW before its first paper session
RMW_ID = "RMW-FR"  # lab M0022-W-TV16 in fractional shares (monthly pick, weekly brake)
# 013, the roster the owner chose for the first paper night (2026-10-07). A, F4-FR and F1-FR go;
# these three join RMW-FR and C. See the block comment above SEED_ROWS' 013 section for why each.
RAW_ID = "RAW-FR"  # lab M0007-N20-RAW in fractional shares: RMW's engine with no brake
MOM_ID = "MOM-FR"  # lab M0002-REL-85 in fractional shares; replaces F4-FR
MVW_ID = "MVW-FR"  # lab M0008-N30-C07 in fractional shares; replaces F1-FR

# 017, the Gotrade-fee rebuild (2026-10-08). Every one of the six live entries above assumed a flat
# 0.1% a side. Sean measured what Gotrade actually charges against 30 of the owner's own receipts
# (sim/costs.py, validated to the cent on both sides) and it is ~2.5x that at best and 5.2x at the
# owner's current $28 slots, because of a $0.10 per-order floor. `cost_model` sits in
# sim.rules.LEVERS_SINCE_PINS at its no-op "flat", so moving a STARTED entry to "gotrade" moves its
# spec digest and store.check_digest refuses its next night. Compliance is therefore SIX NEW IDS
# with fresh clocks -- the rule docs/runbooks/paper-trading.md states and 010, 011 and 013 followed.
# It costs nothing: zero sessions have been stepped, so a fresh clock throws no history away.
BENCHMARK_GT_ID = "SPY-GT"  # the yardstick pays what the methods pay (resume condition 1)
C_GT_ID = "C-GT"  # the DAILY-TRADING CONTROL, permanently (owner, 2026-10-08; resume condition 2)
RMW_GT_ID = "RMW-FR-GT"
RAW_GT_ID = "RAW-FR-GT"
MOM_GT_ID = "MOM-FR-GT"
MVW_GT_ID = "MVW-FR-GT"

#: The bracket rule set the daily control trades under: design section 5's shape, charging Gotrade's
#: measured schedule instead of a flat 0.1% a side. Added by the bracket-path work; this module only
#: names it, and `rules_for` raises UnknownRules if it is not a `sim.rules` preset.
BRACKET_GOTRADE_RULES_ID = "design-v0-gotrade"

#: ``object_name`` of the benchmark: ``backtest.benchmark.buy_and_hold``, which is rules, not an object.
BENCHMARK_OBJECT = "buy_and_hold"

#: The ticker the benchmark entries hold. Split off from :data:`BENCHMARK_ID` by 017: that constant
#: is an entry ID and there are now two benchmark entries, while the SYMBOL is and always was SPY.
#: :func:`spec` writes this, so the retired SPY entry's spec text does not move.
BENCHMARK_SYMBOL = "SPY"
```
**Impact:** `BENCHMARK_ID` is still exported and still `"SPY"`, so `engine/tests/test_paper_roster.py`'s
import and `paper/store.py`'s separate `BENCHMARK_ID` are unaffected. `BRACKET_GOTRADE_RULES_ID` is
the one string Step 0(a) may correct.

---

### Step 2: The funding plan and the benchmark cost model, as roster-owned statements
**File:** `engine/src/seer_engine/paper/roster.py` — insert immediately **before** the `RESOLVER`
docstring comment at :349 (after `MINVAR_PARAMS` at :346).
**Change:** three module-level tables and one accessor. Two of them enter `spec()`, which is why they
are written out here rather than imported: the comment above `FUNDAMENTAL_PARAMS` (:308-325) already
states the rule — a module this one imports becomes an input to a started paper strategy's digest,
and an edit made elsewhere for an unrelated reason would then silently re-digest a live entry and
fail its next night. The equality against the real object is pinned in the test file instead, exactly
as `tests/test_paper_fnd.py` pins `FUNDAMENTAL_PARAMS` against the lab's `COMPOSITE`.
**Code:**
```python
#: The owner's funding plan, as the roster's own statement of it (owner's decision, 2026-10-08).
#:
#: The paper books start at :data:`PAPER_INITIAL_IDR` (10,000,000 IDR) and 5,000,000 IDR more
#: arrives on the **25th of every calendar month**. The 25th is a calendar date, not a session: the
#: deposit lands and then sits until the next month's first session, which is a mean of 7.0 calendar
#: days later and ranges 4 to 10. That idle cash is part of what the owner will actually experience,
#: so it is modelled rather than smoothed away.
#:
#: **Written out here, not imported from ``sim.contributions``,** for the reason given above
#: ``FUNDAMENTAL_PARAMS``: anything this module imports becomes an input to a started paper
#: strategy's spec digest. ``tests/test_paper_roster.py`` -- where importing the backtest side is
#: free -- pins this equal to the schedule ``sim.contributions`` defines, so the two cannot drift
#: apart in silence. It is a dict of plain strings because :func:`spec` is strings and nulls only.
OWNER_FUNDING: dict[str, str] = {
    "amount_idr": "5000000",
    "cadence": "monthly",
    "day_of_month": "25",
}

#: The thirteen entries that existed before the funding plan was modelled (migrations 003-013).
#:
#: Their specs are already written to ``strategies.params`` and their digests are pinned, so they
#: must keep the spec shape they were digested under. :func:`spec` therefore leaves ``funding`` out
#: for exactly these ids and includes it for every other entry -- including every entry ``promote``
#: writes in future, which is the point of stating the exemption rather than the inclusion: a new
#: entry cannot be silently born without its funding plan recorded.
#:
#: **Closed. Never append to it.** An entry funded by some other plan needs a second funding dict
#: that says what that plan is, not an exemption that says nothing.
PRE_FUNDING_IDS: frozenset[str] = frozenset(
    {
        BENCHMARK_ID,
        "A",
        F4_ID,
        F1_ID,
        "C",
        FND_ID,
        F4_FR_ID,
        F1_FR_ID,
        RM_ID,
        RMW_ID,
        RAW_ID,
        MOM_ID,
        MVW_ID,
    }
)

#: The cost model each BENCHMARK entry's simulated fills pay, keyed by roster id.
#:
#: A benchmark row carries no ``rules_id`` -- :func:`from_row` refuses one -- so there is no column
#: on the row for the lever and no :class:`TradeRules` to read it off. It is stated here, as
#: :data:`LAB_PROVENANCE` is, and unlike provenance it **is** part of :func:`spec`: a yardstick that
#: silently changed what its fills cost would turn "beats SPY TR" into a different comparison
#: without moving a digest, and that is precisely what 017 exists to stop.
#:
#: ``SPY`` keeps ``"flat"`` forever: it is retired, it was started on a flat 0.1% a side, and its
#: digest is pinned. ``SPY-GT`` pays Gotrade's measured schedule, the same one the methods pay.
BENCHMARK_COST_MODEL: dict[str, CostModel] = {
    BENCHMARK_ID: "flat",
    BENCHMARK_GT_ID: "gotrade",
}


def benchmark_cost_model(entry_id: str) -> CostModel:
    """The cost model benchmark entry ``entry_id``'s fills pay (:data:`BENCHMARK_COST_MODEL`).

    :class:`BadRosterRow` when the id is not there. Never defaults: a benchmark that quietly fell
    back to ``"flat"`` while every method paid Gotrade is the asymmetric yardstick 017 removes, and
    an unnamed benchmark must stop the night rather than produce a flattering comparison.
    """
    model = BENCHMARK_COST_MODEL.get(entry_id)
    if model is None:
        raise BadRosterRow(
            f"{entry_id!r}: a benchmark entry must name its cost model in "
            f"paper.roster.BENCHMARK_COST_MODEL; known: {', '.join(sorted(BENCHMARK_COST_MODEL))}"
        )
    return model
```
**Impact:** no existing behaviour changes yet — `spec()` does not read these until Step 5.

---

### Step 3: The six successor rows, at the head of `SEED_ROWS`
**File:** `engine/src/seer_engine/paper/roster.py:735-991`
**Change:** insert the six rows immediately after `SEED_ROWS: tuple[RosterRow, ...] = (` at :735, and
renumber `sort` on the thirteen rows that follow. `SEED_ROWS`' source order must equal `ROSTER_IDS`
(the sorted order) — `tests/test_paper_roster.py:394` asserts it — so the live six come first and the
history follows, which is also how the file now reads best.

Sorts: the successors take 1-6 in the live six's existing relative order (SPY, C, RMW, RAW, MOM, MVW);
the thirteen predecessors move to 7-19 keeping their order. `sort` is a display field and is **not**
in :func:`spec`, so renumbering moves no digest — `test_retiring_a_strategy_does_not_move_its_digest`
and the pins prove it.
**Code:** the block to insert after line 735 (`SEED_ROWS: tuple[RosterRow, ...] = (`):
```python
    # 017, the Gotrade-fee rebuild (2026-10-08). Every entry below this block assumed a flat 0.1%
    # a side. Measured from the owner's own Gotrade receipts (sim/costs.py, exact to the cent on
    # both sides of his 2026-10-07 activity), the real schedule is a round trip of 2.500% at $10,
    # 1.036% at his current $28 slot, 0.620% at $50 and 0.493% at $5,000 -- 12.5x, 5.2x, 3.1x and
    # 2.5x the 0.200% assumed. The asymptote is ~2.5x; everything above it is the $0.10 per-order
    # floor, which binds below about $50 an order. His own 20 real buys cost $2.60 to deploy $558
    # -- 0.47% of the book gone before a single round trip.
    #
    # WHY SIX NEW IDS AND NOT SIX EDITS. `cost_model` sits in sim.rules.LEVERS_SINCE_PINS at its
    # no-op "flat", so moving a STARTED entry to "gotrade" changes its spec digest and
    # store.check_digest refuses its next night with a SpecMismatch. That is the rule
    # docs/runbooks/paper-trading.md states and 010, 011 and 013 followed. It costs nothing here:
    # zero paper sessions have ever been stepped, so a fresh clock throws no history away.
    #
    # WHAT ELSE TRAVELS WITH THEM. All six carry the owner's funding plan (OWNER_FUNDING) in their
    # spec from their first night -- 10,000,000 IDR to start and 5,000,000 IDR more on the 25th of
    # each month. Adding that later would have moved their digests and forced a second rebuild.
    #
    # WHAT DOES NOT CHANGE. The books still hold 20 names. The fee case for holding fewer is a
    # two-month transient under the funding plan: measured, by month 3 a 20-name book pays 0.614%
    # and an 11-name book 0.612%. How many names to hold is a question about returns, not fees, and
    # if it is ever answered differently the answer lands as a FURTHER entry under this same rule.
    RosterRow(
        id=BENCHMARK_GT_ID,
        name="SPY",
        sub="S&P 500, buy and hold, real Gotrade fees",
        icon="landmark",
        is_champion=True,
        is_benchmark=True,
        sort=1,
        engine="benchmark",
        rules_id=None,
        object_name=BENCHMARK_OBJECT,
        registry_id=None,
        gate_note=(
            "Benchmark, not a strategy: it has no backtest gate and is never a Seer pick. It "
            "replaces SPY, which bought at a flat 0.1% a side while every method now pays "
            "Gotrade's measured schedule -- a yardstick cheaper than the thing it measures. Over "
            "the lab's dev window at the same real fees SPY returns +350%"
        ),
    ),
    RosterRow(
        id=C_GT_ID,
        name="C · News veto",
        sub="A's picks, LLM can veto on news, daily, real Gotrade fees",
        icon="gavel",
        is_champion=False,
        is_benchmark=False,
        sort=2,
        engine="bracket",
        rules_id=BRACKET_GOTRADE_RULES_ID,
        object_name="STRATEGY_C",
        registry_id=None,
        gate_note=(
            "Backtest gate: not applicable (LLM strategy, design section 1 item 5). On the roster "
            "PERMANENTLY as the daily-trading control (owner, 2026-10-08): it measures how bad "
            "daily trading on Gotrade would have been, which was the owner's original plan. Being "
            "expensive is the finding it exists to produce, so it is never retired on cost "
            "grounds. It answers that question only if it runs on the same starting capital, the "
            "same monthly contributions and the same fee schedule as the monthly books, and it "
            "carries all three"
        ),
        gate_applicable=False,
    ),
    RosterRow(
        id=RMW_GT_ID,
        name="RMW · Braked momentum",
        sub=(
            "Top 20 by rise beyond the market, picked monthly; holds less when jumpy, checked "
            "weekly; fractional shares, real Gotrade fees"
        ),
        icon="activity",
        is_champion=False,
        is_benchmark=False,
        sort=3,
        engine="book",
        rules_id="monthly-rank-weekly-resize-frac-gotrade",
        object_name="WEEKLYBRAKE",
        registry_id=None,
        gate_note=(
            "Lab M0022 dev window only (1996-01-03..2015-10-16), in whole shares at the assumed "
            "0.1% a side: beats SPY TR (+789.2% vs +351.4%), max DD 14.3%, PF 2.06 and 1,589 "
            "trades all pass; failed only DSR >= 0.95 (0.916 at N=110). Re-measured at Gotrade's "
            "real fees (449fa34, report only -- the lab's own N is unchanged) it returns +543% "
            "against SPY's +350% at the same fees, so no verdict moves. Successor of RMW-FR, which "
            "paid the assumed rate; this entry pays Gotrade's measured schedule from its first "
            "night. On paper to test it forward"
        ),
    ),
    RosterRow(
        id=RAW_GT_ID,
        name="RAW · Unbraked momentum",
        sub="Top 20 by rise beyond the market, no brake, monthly, fractional shares, real Gotrade fees",
        icon="zap",
        is_champion=False,
        is_benchmark=False,
        sort=4,
        engine="book",
        rules_id="monthly-hold-frac-gotrade",
        object_name="RESIDMOM",
        registry_id=None,
        gate_note=(
            "Lab M0007 dev window only (1996-01-03..2015-10-16), in whole shares at the assumed "
            "0.1% a side: beats SPY TR (+1,502.2% vs +351.4%), max DD 19.6%, PF 2.16 and 1,596 "
            "trades all pass. It does NOT pass the luck test: 0.914 at the N=85 it was scored at, "
            "0.899 re-scored at today's N=110, just under the 0.90 bar. Never had a test-window "
            "look. Re-measured at Gotrade's real fees (449fa34, report only) it returns +1,126% "
            "against SPY's +350% at the same fees. Successor of RAW-FR, which paid the assumed "
            "rate. On paper as the controlled comparison against RMW-FR-GT: the same book without "
            "the brake"
        ),
    ),
    RosterRow(
        id=MOM_GT_ID,
        name="MOM · Regime momentum",
        sub=(
            "Top 20 by last year's rise, holds less when jumpy for itself, monthly, fractional "
            "shares, real Gotrade fees"
        ),
        icon="trending-up",
        is_champion=False,
        is_benchmark=False,
        sort=5,
        engine="book",
        rules_id="monthly-hold-frac-gotrade",
        object_name="REGIME",
        registry_id=None,
        gate_note=(
            "Lab M0002 dev window only (1996-01-03..2015-10-16), in whole shares at the assumed "
            "0.1% a side: beats SPY TR (+940.1% vs +351.4%), max DD 18.4%, PF 2.33 and 1,148 "
            "trades all pass; failed only the luck test (0.854 at the N=80 it was scored at, 0.828 "
            "at today's N=110). Re-measured at Gotrade's real fees (449fa34, report only) it "
            "returns +763% against SPY's +350% at the same fees. Successor of MOM-FR, which paid "
            "the assumed rate. On paper to test it forward"
        ),
    ),
    RosterRow(
        id=MVW_GT_ID,
        name="MVW · Steady weights",
        sub=(
            "Top 30 by last year's rise, weighted to swing least together, monthly, fractional "
            "shares, real Gotrade fees"
        ),
        icon="scale",
        is_champion=False,
        is_benchmark=False,
        sort=6,
        engine="book",
        rules_id="monthly-hold-frac-gotrade",
        object_name="MINVAR",
        registry_id=None,
        gate_note=(
            "Lab M0008 dev window only (1996-01-03..2015-10-16), in whole shares at the assumed "
            "0.1% a side: beats SPY TR (+726.7% vs +351.4%), max DD 20.0%, PF 2.14 and 1,223 "
            "trades all pass; failed only the luck test (0.817 at the N=74 it was scored at, 0.780 "
            "at today's N=110). Re-measured at Gotrade's real fees (449fa34, report only) it "
            "returns +536% against SPY's +350% at the same fees. Successor of MVW-FR, which paid "
            "the assumed rate. Its drawdown sits exactly on the 20% bar, with no margin. On paper "
            "to test it forward"
        ),
    ),
```
**And** change `sort=` on the thirteen rows that follow, in place, nothing else about them:

| Row (id) | old `sort` | new `sort` |
|---|---|---|
| `BENCHMARK_ID` (`SPY`) | 1 | 7 |
| `"A"` | 2 | 8 |
| `F4_ID` | 3 | 9 |
| `F1_ID` | 4 | 10 |
| `"C"` | 5 | 11 |
| `FND_ID` | 6 | 12 |
| `F4_FR_ID` | 7 | 13 |
| `F1_FR_ID` | 8 | 14 |
| `RM_ID` | 9 | 15 |
| `RMW_ID` | 10 | 16 |
| `RAW_ID` | 11 | 17 |
| `MOM_ID` | 12 | 18 |
| `MVW_ID` | 13 | 19 |

**And** set `status="retired"` on the six rows that are still `active`: `BENCHMARK_ID`, `"C"`,
`RMW_ID`, `RAW_ID`, `MOM_ID`, `MVW_ID`. Add the comment `# 017: superseded by <NEW-ID>, which pays
Gotrade's measured fees` on each. **And** set `is_champion=False, is_benchmark=False` on the
`BENCHMARK_ID` row — both are display fields, neither is in `spec()`, so `SPY`'s digest does not move.

**Impact:** `ROSTER_IDS` becomes
`("SPY-GT", "C-GT", "RMW-FR-GT", "RAW-FR-GT", "MOM-FR-GT", "MVW-FR-GT", "SPY", "A", F4, F1, "C", FND,
F4_FR, F1_FR, "RM-FR", "RMW-FR", "RAW-FR", "MOM-FR", "MVW-FR")` and `active(ROSTER)` becomes the six
successors alone. `SEED_ROWS[1]` is now `C-GT`, not `A` — fixed in Step 8.

---

### Step 4: Lab provenance for the four book successors
**File:** `engine/src/seer_engine/paper/roster.py:511` — append inside `LAB_PROVENANCE`, before the
closing `}`.
**Change:** each successor trades the same lab method and the same recorded variant as its
predecessor, so it names the same trial. The reason says what is new: the fees. `SPY-GT` and `C-GT`
get no entry — the benchmark and the LLM strategy are not lab-derived, exactly as `SPY` and `C`.
**Code:**
```python
    # 017: the Gotrade-fee successors. Each trades the SAME lab method and the SAME recorded
    # variant as the entry it replaces -- the trial behind it is unchanged, and it is still a
    # dev-window row run at the assumed 0.1% a side. What is new is what the PAPER entry pays.
    RMW_GT_ID: LabProvenance(
        method_id="M0022",
        candidate_id="M0022-W-TV16",
        lab_status="rejected",
        basis="owner-override",
        reason=(
            "the same method and variant as RMW-FR, which it replaces, now paying Gotrade's "
            "measured fee schedule instead of the assumed 0.1% a side. It failed only the luck "
            "test -- recorded DSR 0.916 at its recorded N = 110 -- and passed every owner "
            "condition. Re-measured at real fees the dev window returns +543% against SPY's +350% "
            "at the same fees, so the admission is the same admission at an honest price"
        ),
    ),
    RAW_GT_ID: LabProvenance(
        method_id="M0007",
        candidate_id="M0007-N20-RAW",
        lab_status="rejected",
        basis="owner-override",
        reason=(
            "the same method and variant as RAW-FR, which it replaces, now paying Gotrade's "
            "measured fee schedule. It passes all five owner conditions -- max DD 19.6%, inside "
            "the revised 20% bar -- but NOT the lab's luck test: 0.914 at the N = 85 it was scored "
            "at, 0.899 at today's N = 110. It is RMW-FR-GT's own engine with the volatility brake "
            "removed, admitted as the controlled forward comparison at real fees: whether the "
            "brake earns what it costs once the fees are the owner's actual fees"
        ),
    ),
    MOM_GT_ID: LabProvenance(
        method_id="M0002",
        candidate_id="M0002-REL-85",
        lab_status="rejected",
        basis="owner-override",
        reason=(
            "the same method and variant as MOM-FR, which it replaces, now paying Gotrade's "
            "measured fee schedule. It passes all five owner conditions on the dev window and "
            "fails only the luck test -- 0.854 at the N = 80 it was scored at, 0.828 at today's "
            "N = 110. It is the board's total-return-momentum bet, at max DD 18.4% inside the 20% "
            "bar"
        ),
    ),
    MVW_GT_ID: LabProvenance(
        method_id="M0008",
        candidate_id="M0008-N30-C07",
        lab_status="rejected",
        basis="owner-override",
        reason=(
            "the same method and variant as MVW-FR, which it replaces, now paying Gotrade's "
            "measured fee schedule. It passes all five owner conditions and fails only the luck "
            "test -- recorded DSR 0.817 at the N = 74 it was scored at, 0.780 at today's N = 110. "
            "It is the board's one portfolio-construction bet rather than another ranking rule, "
            "and the least correlated with RMW-FR-GT of any variant that passes the five. Its max "
            "DD is 20.0%, exactly the bar, with no margin: that is the risk of this admission"
        ),
    ),
```
**Impact:** `test_every_provenance_matches_the_committed_lab_database` now checks ten method/variant
pairs plus these four; all four name dev trials that already exist and are ineligible, so it passes
unchanged. `LAB_DERIVED` in the test grows by four (Step 8).

---

### Step 5: `spec()` carries the funding plan and the benchmark's cost model
**File:** `engine/src/seer_engine/paper/roster.py:1045-1073`
**Change:** two conditional keys, both suppressed for the thirteen grandfathered entries so their
digests are byte-identical. This is the same device `rules_dict` already uses for
`LEVERS_SINCE_PINS`, moved up one level from a field to an entry.
**Code:** replace the whole of `spec` with:
```python
def spec(e: RosterEntry) -> dict[str, Any]:
    """The frozen spec of ``e`` (contract C2 ``params.spec``): JSON-ready, strings and nulls only.

    Two keys are conditional, and both are conditional for the same reason the levers in
    ``sim.rules.LEVERS_SINCE_PINS`` are: a fact added after an entry's digest was pinned must not
    move that digest, or ``store.check_digest`` refuses the entry's next paper night.

    - ``funding`` (017) is present for every entry except the thirteen in :data:`PRE_FUNDING_IDS`,
      which were digested before the owner's contribution plan was modelled. Stating the exemption
      rather than the inclusion means a future promoted entry carries its funding plan by default
      and cannot be born without it.
    - a ``benchmark`` entry states what its fills cost: ``cost_rate`` while it is on the old flat
      rate, ``cost_model`` once it is on Gotrade's measured schedule
      (:data:`BENCHMARK_COST_MODEL`). The retired ``SPY`` keeps ``cost_rate``, so its spec text is
      unchanged to the byte.
    """
    if e.engine == "benchmark":
        params: dict[str, str] = {
            "symbol": BENCHMARK_SYMBOL,
            "entry": "open",
            "shares": "whole",
            "dividends": "reinvest",
        }
        model = benchmark_cost_model(e.id)
        if model == "flat":
            params["cost_rate"] = str(COST_RATE)
        else:
            params["cost_model"] = model
        object_id = None
    else:
        params = dict(e.params.as_dict())
        object_id = e.obj.id
    registry_digest = None
    if e.registry_id is not None:
        registry_digest = candidate_digest(next(c for c in REGISTRY if c.id == e.registry_id))
    out: dict[str, Any] = {
        "id": e.id,
        "engine": e.engine,
        "object": e.object_name,
        "object_id": object_id,
        "registry_id": e.registry_id,
        "registry_digest": registry_digest,
        "rules_id": e.rules_id,
        "rules": None if e.rules is None else rules_dict(e.rules),
        "params": params,
        "initial_idr": str(PAPER_INITIAL_IDR),
    }
    if e.id not in PRE_FUNDING_IDS:
        out["funding"] = dict(OWNER_FUNDING)
    return out
```
**Impact:** `spec_text` sorts keys, so insertion order does not matter. Measured before this change:
`SPY`'s spec text is
`{"engine":"benchmark","id":"SPY","initial_idr":"10000000","object":"buy_and_hold","object_id":null,"params":{"cost_rate":"0.001","dividends":"reinvest","entry":"open","shares":"whole","symbol":"SPY"},"registry_digest":null,"registry_id":null,"rules":null,"rules_id":null}`
— the `flat` branch reproduces it exactly.

---

### Step 6: The module docstring states the rebuild
**File:** `engine/src/seer_engine/paper/roster.py:22-26` and `:47-59`
**Change:** the docstring claims `SEED_ROWS` is "the six rows 003/004/006/007 write" (it is nineteen
now) and does not mention the funding plan or the benchmark cost model, both of which are in the
spec. Replace the paragraph at :22-26 with:
```python
:data:`SEED_ROWS` is every row ``db/migrations/003_paper.sql`` through ``017_roster_real_fees.sql``
write, as data, in ``sort`` order -- the six entries that trade first, then the thirteen the
Gotrade-fee rebuild and its predecessors retired. :data:`ROSTER` is ``from_rows(SEED_ROWS)``. The
compiled roster and the stored roster therefore travel the *same* builder, and
``tests/test_paper_roster.py`` checks both against a migrated database.
```
and append to the frozen-spec paragraph, after the sentence ending `"...and the starting capital in
IDR."` at :50:
```python
Two parts of the spec are stated by this module rather than read off the row, because the row has no
column for them: :data:`OWNER_FUNDING` (the money that arrives after the start -- 5,000,000 IDR on
the 25th of each month) and :data:`BENCHMARK_COST_MODEL` (what a benchmark entry's fills cost, where
there is no ``TradeRules`` to carry ``cost_model``). Both are conditional in :func:`spec` so that no
entry digested before they existed moves: see :data:`PRE_FUNDING_IDS`.
```
**Impact:** documentation only.

---

### Step 7: The wiring layer (index Decision D10)

Phases 3, 4 and 6 each built a capability whose only production call site lives in
`engine/src/seer_engine/commands/paper.py`, and each stated its required change as a **handoff**
rather than editing the file, because `commands/paper.py` is wanted by four phases and two of them
(3 and 4) run concurrently in wave 1. D10 gives the file — and `paper/replay.py`,
`commands/promote.py`, `paper/store.py:1127` and `commands/paper_check.py:200` — to this phase.

**Read every one of those three plan files' Handoffs sections before starting**, and apply the code
they specify, not the code predicted here: `phase-3.md` H1–H3, `phase-4.md` H6, `phase-6.md`
handoffs 1, 2 and 4. Step 0 above greps the merged tree for what actually landed; where the tree and
this plan disagree, **the tree wins and this plan is the thing that was wrong**.

Until this step runs, every capability is complete, tested and **inert**. That is safe only because
every signature those phases added is keyword-with-a-default and because the paper clock is frozen
at zero stepped sessions.

---

#### Step 7a: each bracket night is priced by the roster, not by a module constant (phase 4, R4)

**File:** `engine/src/seer_engine/commands/paper.py:553-555`, `:727-734`, `:777`, `:779`;
`engine/src/seer_engine/commands/promote.py:75`, `:275`
**Change:** four call sites pass the entry's own rules, and `promote` stops filing a `"bracket"`
rule set as a book entry. Reproduced verbatim from `phase-4.md`'s Handoff H6, which is that
planner's own Steps 10 and 11 moved intact.

Without this, `C-GT` would construct, be stored with the right spec digest, and then **pay the flat
rate on every paper night** — a lie inside a frozen digest, and the exact failure R4 exists to end.
`e.rules` is never `None` for a bracket entry (`paper/roster.py:656-657` refuses a bracket row
without a `rules_id`), and every entry on the roster *today* carries `DESIGN_V0`, so this changes no
existing number anywhere.

**Code** — `commands/paper.py:553-555`:

```python
                sized = decide_bracket(
                    pf,
                    _bracket_strategy(conn, e, p, p),
                    e.params,
                    view.history,
                    view.membership.members_on(d),
                    d,
                    rules=e.rules,
                )
```

**Code** — `commands/paper.py:727-734`:

```python
        sized = decide_bracket(
            new_portfolio(cash0),
            _bracket_strategy(conn, e, paper_start, paper_start),
            e.params,
            view.history,
            view.membership.members_on(rd.data_date),
            rd.data_date,
            rules=e.rules,
        )
```

**Code** — `commands/paper.py:777` and `:779`, inside `_step_bracket`:

```python
        night = settle_bracket(
            pf,
            s,
            view.bars_on(s, pf.held_symbols()),
            tonight.splits_on(s),
            view.last_bar_date,
            rules=e.rules,
        )
        store.save_bracket_night(conn, e.id, night.portfolio, night.events, night.snapshot)
        sized = decide_bracket(
            night.portfolio,
            strategy,
            e.params,
            view.history,
            view.membership.members_on(s),
            s,
            rules=e.rules,
        )
```

**Code** — `commands/promote.py:275` and its import at `:75`:

```python
    engine = "bracket" if is_bracket(rules) else "book"
```
```python
from seer_engine.sim.rules import PRESETS, TradeRules, is_bracket
```

**Impact:** no behaviour change for anything on the roster or promotable today — every rule set
`promote` sees is `"book"` or `DESIGN_V0`. This is the line that makes `C-GT` honest.

---

#### Step 7b: the live benchmark reads the entry's cost model (phase 3, R1)

**Files:** `engine/src/seer_engine/paper/store.py:1127-1145`;
`engine/src/seer_engine/commands/paper.py:866-878`
**Change:** phase 3's exit criterion is that `BenchmarkState` carries the cost model so it survives
between nights. **Something has to put it there**, and the roster is the only place that knows which
model `SPY-GT` is on. Phase 3's Handoff H1 specifies both edits and the reconciler assigned both
here (see this phase's header block).

Without it `SPY-GT`'s spec would claim Gotrade while its fills paid flat — a lie inside a digest —
and R1 would be only half satisfied: the methods would pay Gotrade while the yardstick they are
judged against paid 0.1%.

**Code** — `paper/store.py:1127`, the signature and the final construction. The `cost_model` keyword
is keyword-only and defaults to `"flat"`, so `test_paper_store.py`'s existing calls are unchanged:

```python
def load_benchmark(
    conn: psycopg.Connection, strategy_id: str = BENCHMARK_ID, *, cost_model: CostModel = "flat"
) -> BenchmarkState:
    """The benchmark's state: ``paper_state`` + its ``book_positions`` row (none before the
    first session's buy), ``start`` from ``strategies.paper_start``, and ``cost_model`` from the
    caller -- the roster's statement about THIS entry (``roster.benchmark_cost_model``), because
    the fee model is not in ``paper_state`` and a benchmark stepped one night at a time must still
    be paying Gotrade on its thousandth night. StoreError when there is no ``paper_state`` row, no
    ``paper_start`` or more than one position; ``BenchmarkState.__post_init__`` validates the rest."""
    state = _require_state(conn, strategy_id)
    row = read_strategy(conn, strategy_id)
    if row is None or row.paper_start is None:
        raise StoreError(f"{strategy_id} has no paper_start; freeze its spec before loading it")
    positions = read_book_positions(conn, strategy_id)
    if len(positions) > 1:
        raise StoreError(f"the benchmark holds one position, found {[p.symbol for p in positions]}")
    return BenchmarkState(
        start=row.paper_start,
        cash=state.cash_usd,
        equity=state.equity_usd,
        position=positions[0] if positions else None,
        last_session=state.last_session,
        cost_model=cost_model,
    )
```

with `from seer_engine.sim.costs import CostModel` added to `paper/store.py`'s imports if phase 6 has
not already added it. **This is the only hunk this phase writes in `store.py`** — phase 6 owns the
deposit path at `:417`/`:449` and the contributions section, both line-disjoint from `:1127`.

**Code** — `commands/paper.py:866-878`, `_step_benchmark`'s first line:

```python
def _step_benchmark(conn: psycopg.Connection, e: RosterEntry, sessions: Sequence[date], tonight: _Tonight) -> None:
    # The cost model is the roster's statement about THIS entry (roster.BENCHMARK_COST_MODEL), not a
    # module default: SPY was started on a flat 0.1% a side and keeps it (invariants 3 and 8), SPY-GT
    # pays Gotrade's measured schedule. The frozen spec records the same value, so what is pinned and
    # what is charged are one statement (017).
    bench = store.load_benchmark(conn, e.id, cost_model=roster.benchmark_cost_model(e.id))
```

with `from seer_engine.paper import roster` added to that module's imports if it is not already
there. The rest of the function is unchanged — `step_benchmark` reads `state.cost_model` and carries
it forward, which is phase 3's design, so there is no per-session argument to thread.

**Step 0(c) may contradict this.** If phase 3 shipped a different mechanism (a `RosterEntry` field, a
`step_benchmark` keyword), use what it shipped and keep this step's *assertion* in Step 8's
`test_the_benchmark_entry_and_the_stepper_agree`, which pins the roster's statement to whatever the
stepper actually reads. The one unacceptable outcome is `SPY-GT` stepping at `"flat"`.

**Impact:** `SPY` keeps `"flat"` and its arithmetic is bit-identical; `SPY-GT` pays the schedule its
spec names.

---

#### Step 7c: the night takes the owner's deposit (phase 6, R3)

**File:** `engine/src/seer_engine/commands/paper.py` — once per entry before the session loop, and
at the top of each of the three session loops
**Change:** phase 6 built `accrue_contributions` / `apply_contributions` / `deposit_book` and tested
them; nothing calls them in production until the night does. Reproduced from `phase-6.md`'s
Handoff 1, with the schedule's real names from `phase-5.md`.

This is why this phase's exit criteria say the successor entries carry the contribution schedule
**from their first night**: a roster entry created without the wiring would need rebuilding again,
and rebuilding a *started* entry is what invariant 3 forbids.

**Code** — once per entry, per night, before the session loop (the one place the schedule object is
read; note **`dates_in`**, phase 5's inclusive-both-ends method, not a `due_dates` that does not
exist):

```python
from seer_engine.sim.contributions import OWNER_MONTHLY

store.accrue_contributions(
    conn, e.id,
    OWNER_MONTHLY.dates_in(paper_start, sessions[-1]),
    OWNER_MONTHLY.amount_idr,
    through=sessions[-1],
    usd_idr_on=view.usd_idr_on,
)
```

**Code** — at the top of each session loop, before the engine settles that session. The book engine
(`_step_book`, `commands/paper.py:787`):

```python
        credited = store.apply_contributions(conn, e.id, s)
        if credited:
            book = deposit_book(book, credited)
```

with `deposit_book` added to the `seer_engine.paper.book` import. The bracket engine
(`_step_bracket`) and the benchmark (`_step_benchmark`) take one-line adapters:

```python
        # sim.Portfolio (bracket):
        credited = store.apply_contributions(conn, e.id, s)
        if credited:
            pf = replace(pf, cash=pf.cash + credited, equity=pf.equity + credited)
```
```python
        # paper.benchmark.BenchmarkState:
        credited = store.apply_contributions(conn, e.id, s)
        if credited:
            bench = replace(bench, cash=bench.cash + credited, equity=bench.equity + credited)
```

**CASH *AND* EQUITY — this is the load-bearing half, and it is the one thing in this step that is
easy to get wrong.** Both engines size from the last snapshot's **equity**: `sim/sizing.py:137` is
`slot_budget = q(portfolio.equity / SLOTS)` and `sim/book.py:536` is `equity = book.equity`. A
deposit credited to cash alone would sit in the book **permanently under-deployed** — the money
would be there and nothing would ever size against it. `paper.book.deposit_book` already raises both
(phase 6, Step 7); these two adapters must match it. Phase 5 applies the same rule in both backtest
runners, and phase 6's exit criteria assert it; this is the third place it has to hold.

`apply_contributions` deliberately does **not** write `paper_state` (phase 6's D6e): the night's own
`save_*_night` is the only writer of `cash_usd`, so the money is recorded once, carried once and
written once. It also refuses a session at or before `paper_state.last_session` with a `StoreError`
(phase 6's D6f, invariant 3), so a settled session can never be credited.

**Impact:** nothing changes for any entry that has no `paper_contributions` row — which is every
entry today, because the table lands empty and paper is paused. The first deposit reaches a book on
the first night after the owner resumes.

---

#### Step 7d: `seer paper check` replays what the entry really is (phases 4 and 6)

**Files:** `engine/src/seer_engine/paper/replay.py:280`, `:290`, `:325`, `:406`;
`engine/src/seer_engine/commands/paper_check.py:200`
**Change:** `expected_bracket` hard-codes `DESIGN_V0` and all three `expected_*` builders rebuild
from `cash0` with no deposits. Both are measured gaps that bite the **first night after the owner
resumes**, which is precisely when he is least able to tell a real break from a replay artefact.

- `replay.py:290` is `run_rules(fixed, strategy, params, DESIGN_V0, start, last, …)`. For `C-GT`
  that replays Gotrade's daily control **at the flat rate**, so `judge` reports a mismatch on every
  session. Phase 5 added `run_backtest(..., rules=...)` and made `run_rules` dispatch on
  `is_bracket`, so the fix is to pass the head's own rules.
- All three builders start at `cash0 = initial_cash_usd(PAPER_INITIAL_IDR, head.usd_idr)` and never
  receive a deposit. Once a contribution lands, the stored record holds money the replay does not,
  and `judge` reports a mismatch on every session **after** it. Phase 5 added `contributions=` to
  both runners and phase 7 added it to `buy_and_hold`; the **dated dollars** come from
  `store.read_contributions` (phase 6), carried onto `PaperHead` as
  `tuple((c.session_date, c.amount_usd) for c in … if c.applied)`, ascending. Pass the **record,
  not the schedule** (D18): each of those dollars was frozen at `usd_idr_on(its landing session)`,
  and re-deriving them from `OWNER_MONTHLY` at `head.usd_idr` would reproduce a different number
  every time the rupiah had moved — which is the mismatch this step exists to remove, not cause.
  `if c.applied` matters for the same reason it does in phase 6's Step 10: an accrued row that no
  session has credited is in no stored snapshot either.

**Code** — `replay.py:280` and `:290`:

```python
def expected_bracket(
    market: Market,
    strategy: Strategy,
    params: Any,
    head: PaperHead,
    *,
    rules: TradeRules = DESIGN_V0,
    contributions: Sequence[tuple[date, Decimal]] = (),
) -> Records:
    """The bracket record ``run_rules(rules)`` gives over the head's window, plus the next decision.

    ``rules`` is the entry's own rule set -- ``DESIGN_V0`` for C, ``DESIGN_V0_GOTRADE`` for C-GT.
    Replaying a Gotrade entry at the flat rate disagrees with the stored record on every session.

    ``contributions`` is the deposits this entry has ALREADY received, as ``(session, usd)`` pairs
    from ``store.read_contributions`` -- the record, never the schedule. Each amount was frozen at
    the rate of the day it landed; re-deriving it here at one rate would disagree with the stored
    record the first time the rupiah moved (plan set Decision D18).
    """
```
```python
        run = run_rules(
            fixed, strategy, params, rules, start, last,
            initial_idr=PAPER_INITIAL_IDR, contributions=contributions,
        )
```

and the `isinstance(run, RunResult)` check below it reports `rules.id` rather than the literal
`"DESIGN_V0"`.

`expected_book` (`:325`) and `expected_benchmark` (`:406`) each gain the same keyword-only
`contributions` and pass it to `run_rules` / `buy_and_hold` respectively — the same tuple of
`(session, usd)` pairs reaches all three, because phase 5's `credit_for` and phase 7's
`buy_and_hold` both take that shape. The caller resolves both from the head: the rules from
`roster.rules_for(head.rules_id)` and the deposits from `store.read_contributions(conn, e.id)`,
filtered to `c.applied` and sorted by `session_date`. It is `()` for the thirteen grandfathered
entries, which have no `paper_contributions` rows at all — and `()` is also what makes every replay
on today's tree bit-identical to today's.

The entry's frozen spec (`roster.OWNER_FUNDING`, Step 2) is **not** read here. It states the plan the
entry was born under, which is the right thing to put in a digest and the wrong thing to replay
with; the rows are what the night actually credited.

**Code** — `commands/paper_check.py:200`, one label line. `state.initial_cash_usd` is *capital on
day 0*, not *capital in*, the moment deposits exist:

```python
        "initial_cash": state.initial_cash_usd,   # capital on day 0, NOT capital in
        "deposited": sum((c.amount_usd for c in store.read_contributions(conn, e.id) if c.applied), Decimal("0.0000")),
```

**Impact:** inert today — zero sessions stepped, so `paper check` has nothing to replay. It is a
correctness fix landing ahead of the first night that needs it, which is the shape of this whole
plan set.

---

#### Step 7e: what this step must leave true

Checkable, before the phase is called done:

```bash
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
PYTHONPATH=engine/src python -c "import seer_engine.commands.paper, seer_engine.commands.promote, \
  seer_engine.commands.paper_check, seer_engine.paper.replay, seer_engine.paper.store"
grep -n 'DESIGN_V0' engine/src/seer_engine/paper/replay.py        # only as a default, never a literal arg
grep -c 'rules=e.rules' engine/src/seer_engine/commands/paper.py  # expect 4
git diff engine/src/seer_engine/paper/store.py                     # only the load_benchmark hunk
```

### Step 8: The test file — pins, sets, and three new assertions
**File:** `engine/tests/test_paper_roster.py`
**Change:** six edits to existing code and three new tests.

**(a) ids and sets, :65-80.** Add the six successor ids and rewrite the two lifecycle tuples:
```python
# 017: the Gotrade-fee rebuild. Every entry above assumed a flat 0.1% a side; these six pay the
# schedule measured from the owner's own receipts (sim/costs.py). New ids with fresh clocks,
# because cost_model is a LEVERS_SINCE_PINS lever and moving a started entry's digest would fail
# its next night. Zero sessions had been stepped, so the fresh clocks cost no history.
SPY_GT = "SPY-GT"
C_GT = "C-GT"
RMW_GT = "RMW-FR-GT"
RAW_GT = "RAW-FR-GT"
MOM_GT = "MOM-FR-GT"
MVW_GT = "MVW-FR-GT"
#: every entry that ever traded under the assumed flat rate, plus the three 013 retired; none of
#: them ever stepped a paper session, and every one of them keeps every row it wrote.
RETIRED = (F4, F1, FND, RM, "A", F4_FR, F1_FR, "SPY", "C", RMW, RAW, MOM, MVW)
ACTIVE_IDS = (SPY_GT, C_GT, RMW_GT, RAW_GT, MOM_GT, MVW_GT)
```

**(b) `PINS`, :85-106.** Keep the thirteen existing entries **verbatim** — they are the proof that
nothing moved — and append the six, computed in Step 9:
```python
    # 017: the Gotrade-fee successors. They digest differently from their predecessors for two
    # reasons at once -- rules.cost_model is "gotrade" (SPY-GT: a "cost_model" param instead of a
    # "cost_rate"), and the spec carries the owner's funding plan. The thirteen pins above are
    # UNCHANGED, which is the thing this block has to prove: adding six entries and renumbering
    # every `sort` must not move one live digest.
    SPY_GT: "<computed in Step 9>",
    C_GT: "<computed in Step 9>",
    RMW_GT: "<computed in Step 9>",
    RAW_GT: "<computed in Step 9>",
    MOM_GT: "<computed in Step 9>",
    MVW_GT: "<computed in Step 9>",
```

**(c) `test_the_roster_is_the_handover_entries_in_sort_order`, :125-128:**
```python
def test_the_roster_is_the_handover_entries_in_sort_order():
    assert ROSTER_IDS == (
        SPY_GT, C_GT, RMW_GT, RAW_GT, MOM_GT, MVW_GT,
        "SPY", "A", F4, F1, "C", FND, F4_FR, F1_FR, RM, RMW, RAW, MOM, MVW,
    )
    assert [e.sort for e in ROSTER] == list(range(1, 20))
    assert "B" not in ROSTER_IDS
```

**(d) `test_spy_is_the_only_champion_and_the_only_benchmark`, :131-133.** The flags moved to the
successor; the retired SPY keeps its rows and loses only its display flags:
```python
def test_spy_is_the_only_champion_and_the_only_benchmark():
    assert [e.id for e in ROSTER if e.is_champion] == [SPY_GT]
    assert [e.id for e in ROSTER if e.is_benchmark] == [SPY_GT]
    # 017 moved both flags off the retired SPY. Neither is in the spec, so its digest did not move.
    assert spec_digest(spec(entry("SPY"))) == PINS["SPY"]
```

**(e) the two positional `SEED_ROWS[1]` lookups, :483 and :489.** `SEED_ROWS[1]` is `C-GT` now.
Replace both with a lookup by id:
```python
def _seed(sid: str) -> RosterRow:
    """The seed row with id ``sid``. By id, not by index: 017 put the live six at the head."""
    return next(r for r in SEED_ROWS if r.id == sid)


def test_retiring_a_strategy_does_not_move_its_digest():
    """Invariant 2 and 3: status and paper_end are lifecycle, never spec."""
    retired = from_row(dataclasses.replace(_seed("A"), status="retired", paper_end=date(2026, 10, 2)))
    assert spec_digest(spec(retired)) == PINS["A"]
    assert strategy_params(retired) == strategy_params(entry("A"))


def test_a_corrected_gate_note_does_not_move_a_digest():
    corrected = from_row(dataclasses.replace(_seed("A"), gate_note="corrected, still failed"))
    assert spec_digest(spec(corrected)) == PINS["A"]
    assert corrected.gate_note == "corrected, still failed"
    assert backtest_gate(corrected) == backtest_gate(entry("A"))
    assert strategy_params(corrected) == strategy_params(entry("A"))
```

**(f) `test_active_drops_retired_entries_and_keeps_order`, :466-478.** It retires `RMW`, which 017
already retired. Point it at a live entry instead:
```python
def test_active_drops_retired_entries_and_keeps_order():
    # RAW_GT, not A or RMW: both are retired in SEED_ROWS already, so retiring them again would
    # assert nothing. Retiring a LIVE entry is the case that matters -- it is what
    # `promote --retire` does on every future swap.
    rows = tuple(
        dataclasses.replace(r, status="retired", paper_end=date(2026, 10, 2)) if r.id == RAW_GT else r
        for r in SEED_ROWS
    )
    entries = from_rows(rows)
    assert [e.id for e in entries] == list(ROSTER_IDS)  # retired rows are never dropped
    assert [e.id for e in active(entries)] == [SPY_GT, C_GT, RMW_GT, MOM_GT, MVW_GT]
    raw = next(e for e in entries if e.id == RAW_GT)
    assert (raw.status, raw.paper_end) == ("retired", date(2026, 10, 2))
```

**(g) `test_lookbacks`, :283-290.** The successors run the same objects, so the same lookbacks:
```python
def test_lookbacks():
    assert {e.id: e.lookback for e in ROSTER} == {
        SPY_GT: 1, C_GT: 200, RMW_GT: 426, RAW_GT: 401, MOM_GT: 379, MVW_GT: 253,
        "SPY": 1, "A": 200, F4: 253, F1: 200, "C": 200, FND: 20, F4_FR: 253, F1_FR: 200,
        RM: 401, RMW: 426, RAW: 401, MOM: 379, MVW: 253,
    }
    # FND's lookback is the 20-bar dollar-volume window: a filing's availability is its `filed`
    # date, not a bar count. RMW's 426 is the roster's longest, which is why the night loads 640
    # calendar days, not 550 -- unchanged by 017, which adds no new object.
    assert MAX_LOOKBACK_BARS == 426
```

**(h) the two `promoted_from` sets, :524 and :701.** Four more rows name their method:
```python
    assert {r.id for r in rows.values() if r.promoted_from is not None} == {
        FND, RM, RMW, RAW, MOM, MVW, RMW_GT, RAW_GT, MOM_GT, MVW_GT,
    }
```
and at :526-528 add:
```python
    assert (rows[RAW_GT].promoted_from, rows[MOM_GT].promoted_from, rows[MVW_GT].promoted_from) == (
        "M0007", "M0002", "M0008",
    )
    assert rows[RMW_GT].promoted_from == "M0022"
```
and at :538 the active set becomes `list(ACTIVE_IDS)` (it already reads that way).

**(i) `LAB_DERIVED` / `NOT_LAB_DERIVED`, :567-570:**
```python
LAB_DERIVED = (F4, F1, FND, F4_FR, F1_FR, RM, RMW, RAW, MOM, MVW, RMW_GT, RAW_GT, MOM_GT, MVW_GT)
#: And the five that are not: the two benchmark entries, C and its Gotrade successor (the LLM
#: strategy the quant gate does not apply to), and A, which predates the lab.
NOT_LAB_DERIVED = ("SPY", SPY_GT, "A", "C", C_GT)
```

**(j) three new tests.** Append at the end of the file:
```python
# ---- 017: the Gotrade-fee rebuild ---------------------------------------------------------------


def test_every_active_entry_pays_gotrade_and_nothing_retired_changed():
    """R1: every entry that trades pays the fees the owner actually pays, SPY included.

    The thing the whole rebuild exists for, asserted as one statement. A book or bracket entry says
    so through its rule set's `cost_model`; the benchmark, which has no rule set, says so through
    `BENCHMARK_COST_MODEL`, and both end up in the spec.
    """
    for e in active(ROSTER):
        if e.engine == "benchmark":
            assert benchmark_cost_model(e.id) == "gotrade", e.id
            assert spec(e)["params"]["cost_model"] == "gotrade", e.id
            assert "cost_rate" not in spec(e)["params"], e.id
        else:
            assert e.rules is not None and e.rules.cost_model == "gotrade", e.id
            assert spec(e)["rules"]["cost_model"] == "gotrade", e.id
    # and the six predecessors are retired, not deleted: every one keeps its row and its digest.
    for old, new in (("SPY", SPY_GT), ("C", C_GT), (RMW, RMW_GT), (RAW, RAW_GT),
                     (MOM, MOM_GT), (MVW, MVW_GT)):
        assert entry(old).status == "retired", old
        assert spec_digest(spec(entry(old))) == PINS[old], old
        assert entry(new).status == "active", new
        assert spec_digest(spec(entry(new))) != PINS[old], new


def test_the_daily_control_stays_and_is_funded_like_the_books():
    """The owner's standing instruction, 2026-10-08, as a test rather than a comment.

    C exists to measure how bad daily trading on Gotrade would have been -- it was his original
    plan. Being expensive is the finding, so it is never retired on cost grounds. It only answers
    the question if it runs on the same money as the books it is compared against: the same start,
    the same deposits and the same fee schedule.
    """
    c = entry(C_GT)
    assert c.status == "active" and c.engine == "bracket"
    assert c.rules is not None and c.rules.cadence == "daily"
    assert c.rules.cost_model == "gotrade"
    assert c.gate_applicable is False and backtest_gate(c) == {"passed": False, "applicable": False}
    s = spec(c)
    books = [spec(e) for e in active(ROSTER) if e.engine == "book"]
    assert books, "the control needs books to be a control of"
    assert all(s["initial_idr"] == b["initial_idr"] for b in books)
    assert all(s["funding"] == b["funding"] for b in books)


def test_the_funding_plan_is_the_schedule_the_engine_actually_runs():
    """`OWNER_FUNDING` is written out in `paper/roster.py` and must never drift from the object.

    The roster may not import `sim.contributions` -- anything it imports becomes an input to a
    started paper strategy's digest, and an edit made for a backtest reason would silently
    re-digest a live entry (the same rule as `FUNDAMENTAL_PARAMS`). So the equality is pinned
    HERE, where importing the backtest side is free.
    """
    # Phase 5's value object. The names are read off `phase-5.md`, not guessed: the module is
    # `seer_engine.sim.contributions`, the class `ContributionSchedule(amount_idr, day_of_month=25)`
    # and the instance `OWNER_MONTHLY`. (This plan's draft said `OWNER_PLAN`; the reconciler
    # corrected it on 2026-10-08.)
    from seer_engine.sim.contributions import OWNER_MONTHLY

    assert OWNER_FUNDING["amount_idr"] == str(OWNER_MONTHLY.amount_idr)
    assert OWNER_FUNDING["day_of_month"] == str(OWNER_MONTHLY.day_of_month)
    # `cadence` has no counterpart on the object: `ContributionSchedule` is monthly BY
    # CONSTRUCTION -- it has a `day_of_month` and nothing else -- so the spec's "monthly" is this
    # roster's own prose for a reader of the frozen spec, not a field that can drift. Asserted as a
    # literal so it cannot quietly become something the object does not mean.
    assert OWNER_FUNDING["cadence"] == "monthly"
    assert OWNER_MONTHLY.dates_in(date(2026, 10, 1), date(2026, 12, 31)) == (
        date(2026, 10, 25), date(2026, 11, 25), date(2026, 12, 25),
    )
    # and the funding plan is in the spec of every entry that is not grandfathered, and of none
    # that is -- which is what keeps the thirteen pinned digests where they are.
    assert set(PRE_FUNDING_IDS) == {
        "SPY", "A", F4, F1, "C", FND, F4_FR, F1_FR, RM, RMW, RAW, MOM, MVW,
    }
    for e in ROSTER:
        assert ("funding" in spec(e)) == (e.id not in PRE_FUNDING_IDS), e.id


def test_a_benchmark_entry_must_name_its_cost_model():
    with pytest.raises(BadRosterRow, match="BENCHMARK_COST_MODEL"):
        benchmark_cost_model("SPY-NOT-A-REAL-ENTRY")
```
Add `BENCHMARK_COST_MODEL`, `OWNER_FUNDING`, `PRE_FUNDING_IDS`, `benchmark_cost_model` to the
`seer_engine.paper.roster` import list at :25-49.

**Impact:** `test_the_funding_plan_is_the_schedule_the_engine_actually_runs` is the one place this
phase touches phase 5's names. If `sim.contributions` spells them differently, correct the three
attribute reads — `OWNER_FUNDING`'s values are the owner's decision and do not change.

---

### Step 9: Compute the six pins
**File:** `engine/tests/test_paper_roster.py:85-112` — replace the six `<computed in Step 9>`
placeholders.
**Change:** the six digests cannot be written in advance: they depend on phase 4's preset id and on
`OWNER_FUNDING`'s exact field list. Compute them from the tree, and check in the same breath that the
thirteen old ones did not move.
**Code:**
```bash
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
PYTHONPATH=engine/src python - <<'PY'
from seer_engine.paper.roster import ROSTER, PRE_FUNDING_IDS, spec, spec_digest
print("---- paste the six into PINS ----")
for e in ROSTER:
    if e.id not in PRE_FUNDING_IDS:
        print(f'    {e.id.replace("-","_")}: "{spec_digest(spec(e))}",')
print("---- the thirteen, which must be unchanged ----")
for e in ROSTER:
    if e.id in PRE_FUNDING_IDS:
        print(f'    "{e.id}": "{spec_digest(spec(e))}",')
PY
```
Diff the second block against the `PINS` entries already in the file. **Any difference there is a
bug in this phase, never a pin to update** — it means a live entry's digest moved and
`store.check_digest` would refuse its next night.

**Measured now, before the funding key and before phase 4's preset exists**, as a sanity datum for
the implementer: the four book successors already construct against the two Gotrade presets that
`sim/rules.py:203-206` ships today, carry `cost_model: "gotrade"` in their spec, and move **no**
legacy digest. Command and output:
```
$ PYTHONPATH=engine/src python -c '...from_rows(SEED_ROWS + four -GT book rows)...'
legacy digests moved: none
RAW-FR-GT  rules_id=monthly-hold-frac-gotrade                  digest=a811627f73fc14fb...
MOM-FR-GT  rules_id=monthly-hold-frac-gotrade                  digest=685a7898bdfd4911...
MVW-FR-GT  rules_id=monthly-hold-frac-gotrade                  digest=17ad89bc0c6c083f...
RMW-FR-GT  rules_id=monthly-rank-weekly-resize-frac-gotrade    digest=d1ce24d9b15c4560...
```
Those four prefixes are **not** the pins — they predate the `funding` key — but if the real pins
differ from them in any way other than the funding key, something else changed and is worth finding.
**Impact:** the pins are now facts about the tree, and the thirteen are proof of the invariant.

---

### Step 10: `db/migrations/017_roster_real_fees.sql`
**File:** `db/migrations/017_roster_real_fees.sql` (new)
**Change:** the display rows, in 013's style, byte for byte the `SEED_ROWS` rows
(`test_the_migration_rows_equal_the_seed_rows` compares the whole row, not just the display fields).
Four statements: insert six, retire six, move the two display flags off `SPY`, renumber `sort`.
**Code:**
```sql
-- Seer schema v17: the roster pays Gotrade's real fees (owner, 2026-10-08).
--
-- Every entry on the roster assumed a flat 0.1% a side. Sean measured what Gotrade actually
-- charges against 30 of the owner's own receipts and fitted sim/costs.py to them; it reproduces
-- both sides of his 2026-10-07 activity to the cent ($27.90 buy -> $0.13 charged, receipt $28.03
-- paid; $72.51 sell -> $0.24, receipt $72.27 received). Measured through costs.fee_parts, a round
-- trip costs:
--     $10 -> 2.500%   $28 -> 1.036%   $50 -> 0.620%   $560 -> 0.534%   $5,000 -> 0.493%
-- against the 0.200% assumed: 12.5x, 5.2x, 3.1x, 2.7x, 2.5x. The asymptote is about 2.5x the
-- assumed rate; everything above it is the $0.10 per-order floor, which binds below about $50 an
-- order. The owner's own 20 real buys cost $2.60 to deploy $558 -- 0.47% of the book gone before a
-- single round trip.
--
-- WHY SIX NEW IDS AND NOT SIX EDITS. `cost_model` sits in sim.rules.LEVERS_SINCE_PINS at its no-op
-- "flat", so moving a STARTED entry to "gotrade" changes its frozen spec digest and
-- store.check_digest refuses its next night with a SpecMismatch. docs/runbooks/paper-trading.md
-- states the rule: to change anything about a strategy, add a NEW roster entry with a NEW id; its
-- paper clock starts on its own first night; never edit an entry that has a paper_start and never
-- reset a clock by deleting rows. 010, 011 and 013 are the precedents. The predecessors are
-- RETIRED here, not deleted: a retired entry keeps every row it ever wrote.
--
-- WHY IT IS FREE. Measured against production before this was written: paper_state.last_session is
-- 2026-10-06, pending_session is 2026-10-07, and NO session has ever been stepped --
-- equity_snapshots holds only the starting rows at 560.5067 USD. A fresh clock therefore throws
-- away no paper history at all. Paper has been paused since 2026-10-08 precisely to keep that
-- true, and it stays paused: nightly.yml's PAPER_PAUSED is still 'true', which skips Veto, Paper,
-- Paper check and Explain while Migrate and Nightly (bars) always run. So THIS MIGRATION APPLIES
-- on the next nightly, and nothing else happens -- no paper_start is written and no session is
-- stepped until the owner flips the switch himself.
--
-- WHAT THE SIX ARE.
--   SPY-GT      the yardstick pays what the methods pay. SPY bought at a flat 0.1% a side, so
--               "beats SPY TR" was comparing a cheap benchmark against expensive strategies. A
--               benchmark row carries no rules_id, so its cost model is stated in
--               paper/roster.py's BENCHMARK_COST_MODEL and recorded in its spec.
--   C-GT        the DAILY-TRADING CONTROL, and it stays on this roster permanently (owner's
--               standing instruction, 2026-10-08): "we must always include a daily trading method
--               like C in the roster because I want to see how bad it got if I had used daily
--               trading on Gotrade like my initial plan". Daily trading was his original plan; C
--               is the measured counterfactual, and being expensive is the finding it exists to
--               produce. It is never retired on cost grounds. It answers his question only if it
--               runs on the same starting capital, the same monthly deposits and the same fee
--               schedule as the monthly books, and it carries all three.
--   RMW-FR-GT   lab M0022-W-TV16, RAW-FR-GT lab M0007-N20-RAW, MOM-FR-GT lab M0002-REL-85,
--   RAW-FR-GT   MVW-FR-GT lab M0008-N30-C07 -- the same four methods and the same four recorded
--   MOM-FR-GT   variants that are on the roster today, under the Gotrade fee presets
--   MVW-FR-GT   (monthly-hold-frac-gotrade and monthly-rank-weekly-resize-frac-gotrade).
--
-- WHAT DOES NOT CHANGE. The books still hold 20 names. The fee argument for holding fewer is a
-- two-month transient under the owner's funding plan: measured at 17,841 IDR/USD, by month 3 a
-- 20-name book pays 0.614% and an 11-name book 0.612%. How many names to hold is a question about
-- returns, and if it is ever answered differently the answer lands as a FURTHER entry under the
-- same rule, never as an edit to a running one.
--
-- THE BACKTEST NUMBERS IN THE gate_note COLUMNS, and a caveat that must travel with them. The
-- roster re-measured at real fees (449fa34, report only -- the lab's own N is unchanged) reads
-- RAW +1502% -> +1126%, MOM +940% -> +763%, MVW +727% -> +536%, RMW +789% -> +543%, with SPY at
-- the same fees +350%. All four still beat SPY, so no verdict is overturned. Those averages run
-- over a growth path from a 20M IDR lump to +1126%, so the floor binds hard in the early years and
-- is irrelevant later: the owner sits at the EXPENSIVE end of that path today and these figures
-- UNDERSTATE his near-term drag. The backtest average and today's rate are two different numbers.
--
-- Each row below is byte for byte paper/roster.py's SEED_ROWS (the migration-equality test,
-- tests/test_paper_roster.py). paper_start, the frozen spec and the paper clock are written by the
-- first unpaused night, as for every new entry.
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable, promoted_from) VALUES
  ('SPY-GT', 'SPY', 'S&P 500, buy and hold, real Gotrade fees', 'landmark', true, true, 1, 'benchmark', NULL, 'buy_and_hold', NULL, '<SPY-GT gate_note, exactly as in SEED_ROWS>', true, NULL),
  ('C-GT', 'C · News veto', 'A''s picks, LLM can veto on news, daily, real Gotrade fees', 'gavel', false, false, 2, 'bracket', 'design-v0-gotrade', 'STRATEGY_C', NULL, '<C-GT gate_note>', false, NULL),
  ('RMW-FR-GT', 'RMW · Braked momentum', '<RMW-FR-GT sub>', 'activity', false, false, 3, 'book', 'monthly-rank-weekly-resize-frac-gotrade', 'WEEKLYBRAKE', NULL, '<RMW-FR-GT gate_note>', true, 'M0022'),
  ('RAW-FR-GT', 'RAW · Unbraked momentum', '<RAW-FR-GT sub>', 'zap', false, false, 4, 'book', 'monthly-hold-frac-gotrade', 'RESIDMOM', NULL, '<RAW-FR-GT gate_note>', true, 'M0007'),
  ('MOM-FR-GT', 'MOM · Regime momentum', '<MOM-FR-GT sub>', 'trending-up', false, false, 5, 'book', 'monthly-hold-frac-gotrade', 'REGIME', NULL, '<MOM-FR-GT gate_note>', true, 'M0002'),
  ('MVW-FR-GT', 'MVW · Steady weights', '<MVW-FR-GT sub>', 'scale', false, false, 6, 'book', 'monthly-hold-frac-gotrade', 'MINVAR', NULL, '<MVW-FR-GT gate_note>', true, 'M0008')
ON CONFLICT (id) DO NOTHING;

-- Retiring keeps every row they wrote and the next unpaused night stamps their paper_end. None of
-- the six has a paper_start -- zero sessions were ever stepped -- so there is nothing to stamp and
-- nothing to lose. Their 2026-10-07 pending decisions (80 book_targets rows and 4 orders) stay on
-- the record as what was decided and never acted on; they are not deleted.
UPDATE strategies SET status = 'retired'
WHERE id IN ('SPY', 'C', 'RMW-FR', 'RAW-FR', 'MOM-FR', 'MVW-FR') AND status = 'active';

-- The champion and the benchmark are SPY-GT now. Both are display fields and neither is in the
-- frozen spec, so moving them does not touch the retired SPY's digest.
UPDATE strategies SET is_champion = false, is_benchmark = false WHERE id = 'SPY';

-- Sort is display order: the six that trade come first, then the thirteen that are retired, in the
-- order they were added. Not in the spec either, so no digest moves.
UPDATE strategies AS s SET sort = v.sort
FROM (VALUES
  ('SPY', 7), ('A', 8), ('F4-MOM12-N20-TREND', 9), ('F1-SPY-SMA200-M', 10), ('C', 11),
  ('FND', 12), ('F4-MOM12-N20-TREND-FR', 13), ('F1-SPY-SMA200-M-FR', 14), ('RM-FR', 15),
  ('RMW-FR', 16), ('RAW-FR', 17), ('MOM-FR', 18), ('MVW-FR', 19)
) AS v(id, sort)
WHERE s.id = v.id;
```
**Impact:** the `<...>` placeholders are literal copies of the `SEED_ROWS` strings from Step 3, with
`'` doubled for SQL — `test_the_migration_rows_equal_the_seed_rows` compares every column and will
catch any divergence. If Step 0(a) found a different bracket preset id, `'design-v0-gotrade'` changes
here too.

---

### Step 11: `docs/runbooks/paper-trading.md`
**File:** `docs/runbooks/paper-trading.md:20-37`, `:76`, and a new note before `:288`
**Change:** three edits. This is a document the owner reads, so plain prose, every number with its
meaning, and times in WIB beside UTC.

**(a) the roster table, :20-37.** It still lists `A`, `F4` and `F1`, which 013 retired, and omits
every entry added since. Replace lines 20-37 with:
```markdown
Every entry starts from 10,000,000 IDR, converted at the latest `fx_rates` rate on or before its
first paper night's `data_date`; the rate is stored in `paper_state.usd_idr`. From migration 017
every entry also receives **5,000,000 IDR on the 25th of each month**, which is what the owner
actually does. The deposit lands on the calendar date and sits until the next decision session —
measured, a mean of 7.0 days later, ranging 4 to 10 — and that idle week is modelled on purpose,
because a book that was funded exactly at its rotation would look better than the owner's will.

These six trade. Each pays Gotrade's measured fee schedule (`sim/costs.py`), not the flat 0.1% a
side every earlier entry assumed:

| Id | What it is | Engine | Rules | Backtest gate |
|---|---|---|---|---|
| `SPY-GT` | Buy and hold SPY, dividends reinvested at the ex-date close | benchmark | — | champion and yardstick; not a strategy |
| `C-GT` | Strategy C: A's first 10 ranked candidates for the session, minus every symbol whose nightly news check did not say `allow`; 5-day brackets, 4 slots, **daily** | bracket | `design-v0-gotrade` | not applicable: an LLM strategy (design §1 item 5) |
| `RMW-FR-GT` | Top 20 by rise beyond the market, picked monthly; holds less when jumpy, checked weekly | book | `monthly-rank-weekly-resize-frac-gotrade` | not passed: lab M0022 dev window only |
| `RAW-FR-GT` | The same book as RMW with the volatility brake removed | book | `monthly-hold-frac-gotrade` | not passed: lab M0007 dev window only |
| `MOM-FR-GT` | Top 20 by last year's rise, holding less when jumpy for itself | book | `monthly-hold-frac-gotrade` | not passed: lab M0002 dev window only |
| `MVW-FR-GT` | Top 30 by last year's rise, weighted to swing least together | book | `monthly-hold-frac-gotrade` | not passed: lab M0008 dev window only |

Thirteen earlier entries are **retired**. A retired entry keeps every row it ever wrote and stays on
the leaderboard; it only stops trading. None of the thirteen ever stepped a paper session.

**`C-GT` is permanent.** It is the daily-trading control: the owner's original plan was to trade
daily on Gotrade, and `C-GT` is how he finds out how that would have gone. It is expensive — daily
trading costs roughly 26% a year on a book this size at $28 slots — and that is the finding, not a
reason to remove it. It is never retired on cost grounds, and it only answers the question while it
runs on the same starting capital, the same monthly deposits and the same fees as the books beside
it.

Monthly entries decide only on the first session of a month. A paper start in early October means
the four books hold cash until the open of the next month's first session, and their October shows
0%. That is the same semantics the backtest runner (`run_book`) uses, so it is not a bug.
```

**(b) the schedule line, :76.** This line states a cron that has not existed since `d44fa78`, and it
is the documentary reason the owner expected the nightly at 06:00 WIB and was alarmed one morning
when nothing had run. Replace it with the real schedule, following the table at
`docs/runbooks/data-pipeline.md:391-395`. It is the one line inside the already-open code fence at
:75-109; keep every other line of that diagram and the `│` column alignment below it:

~~~text
GitHub Actions nightly.yml   cron '17 6 * * 2-6' = 06:17 UTC Tue-Sat = 13:17 WIB, reading Mon-Fri's
│                            session; retries '41 9' and '41 12' UTC = 16:41 and 19:41 WIB.
│                            Concurrency group seer-db-writer. The full table, with New York times
│                            as well, is in data-pipeline.md under "Workflows and schedule".
~~~

**(c) a new dated note, inserted immediately before `### Paper trading was paused, then resumed with
RMW (2026-10-07)` at :288:**
```markdown
### The roster pays Gotrade's real fees (migration 017, 2026-10-08)

Every entry before this assumed trading cost 0.1% of each order, on each side. Sean measured what
Gotrade actually charges against 30 of the owner's own receipts and fitted `sim/costs.py` to them.
The model reproduces both sides of his 2026-10-07 activity to the cent: a $27.90 buy is charged
$0.13 (his receipt says $28.03 paid), a $72.51 sell is charged $0.24 (his receipt says $72.27
received).

What a full round trip really costs, by order size — measured by calling `sim.costs.fee_parts`:

| Order | Round trip | Against the 0.200% assumed |
|---|---|---|
| $10 | 2.500% | 12.5× |
| $28 (the owner's slot today) | 1.036% | 5.2× |
| $50 | 0.620% | 3.1× |
| $560 (the whole book today) | 0.534% | 2.7× |
| $5,000 | 0.493% | 2.5× |

Two different things are going on. About 2.5× is the schedule itself and never goes away. Everything
above that is a **$0.10 minimum per order**, which stops mattering above roughly $50 an order. That
floor is why the owner's own 20 real buys cost $2.60 to put $558 to work — 0.47% of the book gone
before a single round trip.

**What it costs the strategies.** The monthly books turn over about a third of themselves a month,
not all of it (measured over the lab's window: RAW 33.6% a month, RMW 33.5%, MVW 25.8%, MOM 24.2%),
so a monthly rotation moves roughly 13 or 14 orders, not 40. At today's slot size that is about 4% a
year of drag, not the 12% a full-turnover reading would suggest.

**What it does to the results.** Re-measured at real fees (a report only — the lab's own scoring is
unchanged), RAW goes from +1,502% to +1,126%, MOM from +940% to +763%, MVW from +727% to +536%, RMW
from +789% to +543%, and SPY at the same fees returns +350%. All four still beat SPY, so nothing
that was decided gets undecided. **One caveat belongs with those numbers**: they average over a
growth path that ends at +1,126%, so the $0.10 floor bites hard in the early years and is irrelevant
later. The owner is at the expensive end of that path today, so those figures understate what he
will pay in the next few months. The backtest average and today's rate are two different numbers and
should not be read as one.

**Why six new entries and not six edits.** `cost_model` is a lever added after the roster's digests
were pinned, so changing it on a running entry changes its frozen spec and `paper` refuses that
entry's next night. The rule above — *a change is a new id* — is exactly this case, so the six live
entries got successors with fresh clocks: `SPY-GT`, `C-GT`, `RMW-FR-GT`, `RAW-FR-GT`, `MOM-FR-GT`
and `MVW-FR-GT`. It cost nothing, because no paper session had ever been stepped: the clocks were
frozen at zero, which is what the pause since 2026-10-08 was for.

**Paper is still paused, deliberately.** `PAPER_PAUSED` is still `'true'` in `nightly.yml`. Migrate
runs while paused, so migration 017 applies on the next nightly and the rebuilt roster simply sits
there — no `paper_start` is written and no session is stepped. The owner flips the switch when he
wants the clocks to start; until then the rebuild stays free. The resume conditions written above
the switch say what holds and what is left.

**The name count did not change.** The books still hold 20. The fee case for holding fewer vanishes
by month three of the funding plan: 20 names cost 0.614% and 11 names cost 0.612%. How many names to
hold is a question about returns, measured separately; if the answer ever differs it arrives as
another roster entry, under the same rule.
```
**Impact:** doc only; nothing imports it.

---

### Step 12: The resume-condition comment above `PAPER_PAUSED`
**File:** `.github/workflows/nightly.yml:46-69` — **the comment only. Line 70 is not touched.**
**Change:** the three resume conditions now hold. Say so, say what is left, and say who does it.
**Code:** replace lines 46-69 with:
```yaml
      # Paper trading switch. Paused 2026-10-07 until paper could run split-cadence rules and RM was
      # replaced by RMW; resumed the same day so every roster strategy starts on the same night.
      # 'true' skips Veto, Paper, Paper check and Explain; Migrate and Nightly (bars) always run.
      #
      # Paused again 2026-10-08 (owner's call) to hold the paper clock at ZERO stepped sessions
      # while the roster was rebuilt to pay Gotrade's real fees. STILL PAUSED, deliberately: the
      # owner flips this switch, not a merge. Migration 017 has landed and the rebuilt roster --
      # SPY-GT, C-GT, RMW-FR-GT, RAW-FR-GT, MOM-FR-GT, MVW-FR-GT -- sits inert while this reads
      # 'true'. No paper_start is written and no session is stepped, so the rebuild stays free.
      #
      # THE THREE RESUME CONDITIONS WRITTEN HERE ON 2026-10-08 NOW ALL HOLD:
      #   1. DONE. paper/benchmark.py threads cost_model through all three of its flat sites, so
      #      the SPY yardstick pays Gotrade's measured schedule and "beats SPY TR" compares two
      #      books paying the same fees. SPY-GT is the entry that uses it.
      #   2. DONE, and C STAYS. The bracket path takes its rule set and charges Gotrade's schedule,
      #      including the $0.10 per-order floor. C-GT is on the roster PERMANENTLY as the
      #      daily-trading control -- the owner's original plan was daily trading, and this is how
      #      he finds out how that would have gone. Daily trading is expensive (~26%/yr on this
      #      book at $28 slots); that is the finding it exists to produce, never a reason to
      #      retire it.
      #   3. DONE for the capital model: the lab starts at the real 10,000,000 IDR, the
      #      +5,000,000 IDR deposit on the 25th of each month is modelled end to end (including
      #      the ~7 idle days before the next rotation), returns are reported money-weighted, and
      #      SPY is fed the same money on the same dates. The rebuilt entries carry that plan in
      #      their frozen specs from their first night, so it never needs a second rebuild.
      #      The NAME COUNT is settled separately and is NOT a blocker: it stays at 20. Measured,
      #      by month 3 of the funding plan 20 names cost 0.614% and 11 names cost 0.612%, so the
      #      fee case for cutting it is gone. If the lab's merits answer ever differs it lands as a
      #      FURTHER roster entry with its own clock, never as an edit to a running one.
      #
      # WHAT REMAINS, and it is the owner's call alone: set this to 'false', commit and push. The
      # first scheduled night after that writes each -GT entry's spec and paper_start and the six
      # clocks start together. The six predecessors are retired, so they stop trading that night;
      # their rows, their specs and their un-stepped 2026-10-07 decisions are kept, never deleted.
      PAPER_PAUSED: 'true'
```
**Impact:** a comment. `grep -c "PAPER_PAUSED: 'true'" .github/workflows/nightly.yml` must still
return `1`.

---

## Verification

**Build / lint:**
```bash
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
PYTHONPATH=engine/src python -c "import seer_engine.paper.roster as r; print(len(r.ROSTER), r.ROSTER_IDS)"
ruff check engine/src/seer_engine/paper/roster.py engine/tests/test_paper_roster.py
```

**Tests** (Postgres must be up:
`docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16`):
```bash
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  python -m pytest engine/tests/test_paper_roster.py -q
PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  python -m pytest engine/tests -q -n auto
```
`PYTHONPATH` is **required** — without it pytest silently tests the main checkout instead of this
branch. Never pass `-o addopts`.

**Manual checks:**
```bash
# the switch is untouched
grep -n "PAPER_PAUSED" .github/workflows/nightly.yml          # exactly one line, value 'true'
# the migration number is free and the file is the only 017
ls db/migrations/01[6-9]*.sql
# costs.py was not touched (invariant 5)
git diff --stat origin/main -- engine/src/seer_engine/sim/costs.py   # empty
# the stale schedule line is gone
grep -n "23:00 UTC" docs/runbooks/paper-trading.md            # no match
grep -n "13:17 WIB" docs/runbooks/paper-trading.md            # one match
# the thirteen legacy digests did not move
git diff origin/main -- engine/tests/test_paper_roster.py | grep '^-.*"[0-9a-f]\{64\}"'   # empty
```
The last one is the sharpest check in this phase: **not one line that removes a 64-hex pin may appear
in the diff.** A removed pin means a started entry's digest moved.

A full `migrate` against a scratch database, then the roster rebuilt from it, is already covered by
`test_the_migration_rows_equal_the_seed_rows` and
`test_the_database_rows_rebuild_the_roster_with_the_pinned_digests`, both of which take the `pg`
fixture.

**Exit criteria:**
1. `active(ROSTER)` is exactly the six `-GT` ids, and every one of them pays `gotrade` — asserted by
   `test_every_active_entry_pays_gotrade_and_nothing_retired_changed`.
2. The thirteen pre-existing pins in `test_paper_roster.py` are unchanged, character for character.
3. `C-GT` is active, daily, on `gotrade`, and shares `initial_idr` and `funding` with the books.
4. `OWNER_FUNDING` equals the schedule `sim.contributions` defines, and appears in the spec of every
   entry that is not grandfathered and none that is.
5. `db/migrations/017_roster_real_fees.sql` exists; `test_the_migration_rows_equal_the_seed_rows`
   passes; nothing is deleted.
6. `PAPER_PAUSED` is still `'true'`, and `git diff .github/workflows/nightly.yml` shows **no change
   to the `PAPER_PAUSED:` line itself** — only to the comment block above it. (Phase 9's drift test
   and phase 11's `sed` both parse that line; reformatting it turns both red.)
7. `docs/runbooks/paper-trading.md` states `17 6 * * 2-6` = 06:17 UTC = 13:17 WIB with both retries,
   and carries the measured fee table with its backtest-average-vs-today caveat.
8. The engine suite reports `0 failed` (allowing for the two known red causes on `main`, which
   phases 1 and 2 fix).

**The wiring layer's exit criteria (Step 7, index Decision D10).** Each closes a handoff another
phase left open, and each is the difference between an entry that *claims* something in a frozen
digest and one that *does* it:

9. **(7a, R4)** `grep -c 'rules=e.rules' engine/src/seer_engine/commands/paper.py` returns **4**, and
   `commands/promote.py:275` reads `is_bracket(rules)`. A `C-GT` night is charged Gotrade's schedule,
   not the flat rate.
10. **(7b, R1)** `_step_benchmark` obtains `SPY-GT`'s cost model from the roster, so the model the
    frozen spec names is the model the fills pay. `test_the_benchmark_entry_and_the_stepper_agree`
    pins the roster's statement to whatever the stepper actually reads. `SPY` is still `"flat"` and
    its arithmetic is bit-identical.
11. **(7c, R3)** The night calls `accrue_contributions` once per entry and `apply_contributions`
    before each session it steps, and a credited deposit raises **cash and equity** on all three
    engines — book, bracket and benchmark. Equity, not cash alone: both engines size from the last
    snapshot's equity (`sim/sizing.py:137`, `sim/book.py:536`), so cash-only crediting leaves the
    deposit permanently under-deployed. Asserted for `deposit_book` by phase 6 and for the two
    adapters here.
12. **(7d)** `paper/replay.py` carries no literal `DESIGN_V0` argument and all three `expected_*`
    builders take the **stored, dated, already-converted** contributions — `(session, usd)` off
    `store.read_contributions`, not `OWNER_MONTHLY` (D18) — so `seer paper check` on a `-GT` entry
    would reconstruct the same record the night wrote even after the rupiah has moved.
    `grep -n 'OWNER_MONTHLY\|ContributionSchedule' engine/src/seer_engine/paper/replay.py` returns
    **nothing**. (Unexercisable today — zero sessions stepped — which is why it is a code-shape
    criterion and not a run.)
13. **(phase 9, R5 — the edge neither phase could see alone)** The six predecessors this phase
    retires keep their 80 `book_targets` rows and 4 `orders` dated 2026-10-07, with
    `pending_decision = true`; they are **not** deleted (invariant 3). Verify, against phase 9's
    landed classifier, that a retired entry's pending decision renders as a **record and never as a
    live instruction**: `panelState(..., retired=true)` is `'spent'` and the panel says the strategy
    has been replaced. Phase 9 handles this generically (its Decision D9.6) and is in wave 1, so this
    phase **verifies** it rather than depending on it. If it does not hold, that is phase 9's bug,
    not this phase's — report it rather than patching `web/` here, which this phase does not own.

---

## Handoffs

- ~~**Phase 3 (R1), the benchmark wiring.**~~ **RESOLVED — Step 7b, this phase.** The reconciler
  gave `commands/paper.py` *and* `paper/store.py:1127` (`load_benchmark`) to this phase under index
  Decision **D10**, and deleted this plan's Branch A / Branch B fork: Branch B is the one that holds,
  because phase 3 ships the capability (`BenchmarkState.cost_model`, `start_benchmark`'s keyword) and
  states in its own Handoff H1 that it edits neither file. Step 0(c) still greps the merged tree, and
  if phase 3 shipped a different mechanism the tree wins — but the *ownership* question is settled
  and no file is left for two phases to argue over.
- ~~**Phase 9 (R5), the un-stepped 2026-10-07 decisions.**~~ **RESOLVED — phase 9 handles it, this
  phase verifies it (exit criterion 13).** Measured against production: 80 `book_targets` rows and 4
  `orders` dated 2026-10-07 belong to entries this phase retires, with `pending_decision = true`.
  This phase does **not** delete them — invariant 3, and they are the record of a decision that was
  made and never acted on. The reconciler carried the edge to phase 9, which added a `retired` input
  to its classifier (its Decision **D9.6**), generically rather than against this rebuild: a retired
  entry is `spent` whatever its `pending_session` says, and its panel says it has been replaced.
  Phase 9 is wave 1 and cannot depend on this phase, which is why the fix lives there and the check
  lives here.
- **Phase 8 (R2), the name count.** Whatever phase 8 measures, these six carry N = 20 (Decision D3).
  If its answer differs it lands as a **further** roster entry with a new id under the rule in
  `paper-trading.md:61-68` — never as an edit to one of these six.
- **`commands/promote.py`** has no mapping from a lab variant's rules to a *bracket* Gotrade preset,
  and its `--fractional` flag maps only the book presets. A future promotion of a bracket method at
  real fees would need one. Not touched here: no promotion in this phase goes through `promote`, and
  phase 4 owns the bracket rule vocabulary.
- **`paper/store.py:59`'s `BENCHMARK_ID = "SPY"`** is a *default argument* for `load_benchmark`, used
  only by `test_paper_store.py`; the production path at `commands/paper.py:867` passes `e.id`. It is
  now a slightly misleading name (there are two benchmark entries). Left alone deliberately: Step 7b
  edits `load_benchmark`'s **signature tail only**, and renaming a module constant phase 6 also
  reads would be a drive-by across a phase boundary for no measured gain.
- **`paper/compare.py`'s deposit-adjusted returns** are **phase 6's**, not this phase's — the
  reconciler assigned them there (phase 6's Step 10) because that phase owns
  `store.read_contributions` and the deposit path whose double-counting is the bug. Nothing in this
  phase touches `compare.py`; if a `-GT` entry's comparison figures ever look wrong after a deposit,
  that is the file to read.

## Rollback

`git revert` this phase's single commit. That restores `roster.py`, the test, the two documents and
`nightly.yml`'s comment, and removes `db/migrations/017_roster_real_fees.sql`.

If 017 has already been applied to a database, undo it there with the inverse of its four statements:
```sql
DELETE FROM strategies WHERE id IN
  ('SPY-GT','C-GT','RMW-FR-GT','RAW-FR-GT','MOM-FR-GT','MVW-FR-GT');
UPDATE strategies SET status = 'active'
  WHERE id IN ('SPY','C','RMW-FR','RAW-FR','MOM-FR','MVW-FR');
UPDATE strategies SET is_champion = true, is_benchmark = true WHERE id = 'SPY';
UPDATE strategies AS s SET sort = v.sort FROM (VALUES
  ('SPY',1),('A',2),('F4-MOM12-N20-TREND',3),('F1-SPY-SMA200-M',4),('C',5),('FND',6),
  ('F4-MOM12-N20-TREND-FR',7),('F1-SPY-SMA200-M-FR',8),('RM-FR',9),('RMW-FR',10),
  ('RAW-FR',11),('MOM-FR',12),('MVW-FR',13)
) AS v(id, sort) WHERE s.id = v.id;
```
The `DELETE` is safe **only while no `-GT` entry has stepped a session** — which is guaranteed while
`PAPER_PAUSED` is `'true'`, because the migration applies but the paper step never runs. That is the
property the pause preserves and the reason this phase can land before the owner has decided
anything. Once he flips the switch and a night steps, deleting a `-GT` row would destroy paper
history and the rollback above stops being available: from then on, undoing this is itself a new
roster entry.

This phase depends on 4, so reverting phase 4 also requires reverting this one. Phases 5, 6 and 7 are
one unit (Decision D4) and this phase depends on 6 and 7; reverting any of them requires reverting
this one too.

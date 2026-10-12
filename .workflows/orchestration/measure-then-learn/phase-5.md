# Phase 5: Near-miss twins under the fixed tape (lab method + run)

**Plan set:** `MEASURE_THEN_LEARN_PLAN.md`
**Analysis:** `20261012-205553-M7T1_code_analyzer.md`
**Satisfies:** R4. The near misses are re-measured under the fixed tape as new pre-registered twins, and the lab answers "were they winning on their picking or on the equal-weight shape?"
**Depends on:** Phase 3 (the three presets; this brings in phases 1 and 2), Phase 4 (`SEER_SV_STORE` and a current survivorship-check store)
**Difficulty:** HARD. The source change is small. What makes it hard is that the run writes to the shared, append-only lab database, the id is minted at run time, and the work spans two checkouts. A mistake after `lab run` cannot be undone.
**Package:** `engine/src/seer_engine/lab/methods`, lab data (`/home/miftah/seer/lab/lab.sqlite`, `/home/miftah/seer/web/data/lab.json`)

---

## Goal

After this phase, one new lab variation method (parent M0030; its id comes from the lab at run time and is written `MNNNN` below) is committed as a pre-registration and has been run on the dev window. It has six variants, all at Gotrade's real fees in fractional shares:
- three near-miss twins on the fixed tape: the resize band measured against each holding's target, and idle cash earning the T-bill rate;
- one no-cash twin, which isolates the cash yield and is the only variant with no owner input;
- two equal-weight 20-name controls on the same tape, one ungated and one behind the same SPY 200-day gate the near misses read.

The method is also survivorship-checked, noted and journaled in plain words with the picking / gate / shape answer, staged, and published on `main`. The test window is never touched.

## Facts this plan rests on (verified in the worktree at `5faa3cb`)

| Fact | Where |
|---|---|
| M0030-SAT100 = `RESIDMOM` + `RAW20` on `MONTHLY_HOLD_FRAC` (flat fee) | `lab/methods/m0030_spy_core_momentum_satellite.py:213-214` |
| M0007-N20-RAW = `RESIDMOM` + `ResidParams(N20, scaled=False)` on `MONTHLY_HOLD` | `lab/methods/m0007_residual_momentum.py:388` |
| `RAW20 = ResidParams(N20, scaled=False)  # M0007-N20-RAW's params, verbatim` | `lab/methods/m0011_raw_residual_own_vol.py:113` |
| So M0030-SAT100 and M0007-N20-RAW share allocator and params, and only the rules differ. **One twin covers both.** | |
| M0021-B70-RAW = `BLEND` + `_blend("0.7", braked=False)` (70% `RESIDMOM`/`RAW20` + 30% `FACTOR`/`CALM20`, both gated) | `lab/methods/m0021_momentum_lowvol_blend.py:36-40,73`; M0029 imports `_blend` the same way (`m0029_blend_fractional.py:21,49`) |
| M0020-W-NOSTOP = `REENTRY` + `ReentryParams(RAW20, None)` on `WEEKLY_HOLD` | `lab/methods/m0020_stop_with_weekly_reentry.py:176` |
| M0120-EW20-ALWAYS = `CLOCK` + `ClockParams("ew", "none")`. It holds the 20 most-traded members, equal weight, **ungated** (`SCREEN.trend=None`) | `lab/methods/m0120_calendar_clock.py:96,211-218,303` |
| Every near miss is gated by `f_factor.trend_on(..., FactorParams(trend=("SPY",200)))` | `m0007_residual_momentum.py:318,333,342`; `strategies/f_factor.py:234` |
| `real_cost_problem` accepts any `engine=="book"` rule set with `cost_model=="gotrade"` | `lab/real_costs.py:61-88` |
| `Method` allows 1..6 candidates, ids `<id>-<suffix>`, family = method id, unique digests inside the method | `lab/method.py:40,158-205` |
| A variant with any owner input is never eligible (D8) | `backtest/dev.py:22-24,440` |
| `lab idea` takes the next id atomically and prints it. When the idea runs, the runner overwrites the idea row's name, family, hypothesis and source from the file | `commands/lab.py:2493-2502`; `lab/runner.py:652-659` |
| `lab stage` writes `web/data/lab.json` **beside the database it is pointed at** and `git add`s both files there | `commands/lab.py:2579-2601` |
| Main's committed-DB test fails when a method that ran has no file: `assert mid in METHODS, f"{mid} ran but its method file is gone"` | `engine/tests/test_lab_methods.py:165` |
| The smoke market carries `EMPTY_SERIES` (no `T13W`); phase 2 Step 11 adds the opt-in `labkit.SMOKE_T13W`, and `test_lab_methods.test_candidate_runs_a_smoke_window` attaches it to any candidate whose rules set `cash_yield` | `engine/tests/labkit.py:44-49`; `backtest/market.py:281,371`; phase 2 Step 11 |
| Dev store and survivorship-check store both carry `market_series.csv` with 5,722 `T13W` rows | `/home/miftah/seer/engine/.research*/market_series.csv` |

Recorded numbers the hypothesis quotes (read-only query of the shared DB, 2026-10-12). "MWR" is the money-weighted return. "vs" is SPY fed the same deposits on the same days.

| Trial | Rules | MWR | vs SPY MWR | worst fall | PF | trades | invested |
|---|---|---|---|---|---|---|---|
| M0032-N20-RAW-FRAC-GT (RAW20, real fee, old band) | monthly-hold-frac-gotrade | 13.68% | 7.19% | 20.65% | 1.98 | 1607 | 0.694 |
| M0030-SAT100 (RAW20, flat fee) | monthly-hold-frac | 14.96% | 7.20% | 20.64% | 2.12 | 1607 | 0.694 |
| M0120-EW20-ALWAYS | monthly-hold-frac-gotrade | 5.66% | 7.19% | 74.41% | 1.15 | 727 | 0.960 |
| M0058-LIQ20-T (gated, 20 most liquid) | monthly-hold-frac-gotrade | 8.12% | 7.19% | 17.64% | 5.20 | 267 | 0.683 |
| M0021-B70-RAW (unfunded, flat, whole shares) | monthly-hold | (CAGR 12.6%) | (7.9%) | 13.98% | 2.25 | 2711 | 0.621 |
| M0020-W-NOSTOP (unfunded, flat, whole shares) | weekly-hold | (CAGR 15.3%) | (7.9%) | 19.27% | 2.11 | 1620 | 0.676 |

### The band arithmetic, which shapes the hypothesis

Phase 1 sets `TARGET_RESIZE_BAND = Decimal("0.20")` of the holding's own target value. In a 20-name equal-weight book every slot is `0.05` of equity, so the new band is `0.20 × 0.05 × equity = 0.01 × equity`. That is **exactly the old `RESIZE_BAND`**.

So for every 20-name equal-weight variant here (RAW20, RAW20-CASH, W-NOSTOP-CASH and both EW20 controls), the band fix is a no-op by construction. Only the blend's sleeves change: momentum slots are `0.7/20 = 3.5%` of equity (band 0.7%), and calm slots are `0.3/20 = 1.5%` (band 0.3%).

The hypothesis says this before the run, and RAW20 against M0032 is the pre-registered check of it. Step 1 refuses to continue if phase 1 shipped a different constant, because the arithmetic sentences would then be wrong (see Step 1).

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `engine/src/seer_engine/lab/methods/mNNNN_near_miss_fixed_tape.py` (the number is filled in from `lab idea` at run time) with:
  - `METHOD` (id `MNNNN`, `source_kind="variation"`, `parent_id="M0030"`, family `near-miss-fixed-tape`, 6 candidates)
  - `GATED`: a new `Allocator` with `id = "MNNNN"`
  - `GatedParams`
  - `MONTHLY_TBAND`, `MONTHLY_TBAND_CASH`, `WEEKLY_TBAND_CASH`, `EW20`, `B70_RAW`, `W_NOSTOP`
- Lab rows in the shared DB:
  - method `MNNNN`, 6 dev trials (with funding, moments and provenance)
  - one survivorship observation
  - up to two `lab costs` observations
  - one analysis note and verdict
  - one `observation` insight
  - one queued `idea` row, which **consumes the id after MNNNN**
  - seen keys `concept:near-miss-fixed-tape-remeasure`, `concept:picking-versus-equal-weight-shape`
- Commits:
  - the pre-registration (method file alone) on the feature branch, pushed to `main`
  - a `lab stage` commit in the main checkout (`lab/lab.sqlite` + `web/data/lab.json`)

**Signature changes:** none.

**Requires (from earlier phases):**
- Phase 1: `TradeRules.resize_basis` exists, and `sim.rules.TARGET_RESIZE_BAND == Decimal("0.20")`.
- Phase 2:
  - `TradeRules.cash_yield` exists, and `rule_owner_inputs(r)` returns `("cash-yield",)` for `cash_yield="T13W"`.
  - The lab runner credits interest from `market.series` (`T13W`).
  - `run_book` refuses a market without the `T13W` series, and phase 2 Step 11 gave the lab smoke test the opt-in `labkit.SMOKE_T13W` series for every candidate whose rules set `cash_yield`, so `test_candidate_runs_a_smoke_window` passes for this method's cash variants with no fixture change here.
- Phase 3: `sim.rules.PRESETS` contains rule sets whose `.id` is exactly `monthly-hold-frac-gotrade-tband`, `monthly-hold-frac-gotrade-tband-cash` and `weekly-hold-frac-gotrade-tband-cash`. All three are `engine="book"`, `fractional=True`, `cost_model="gotrade"` and `resize=True`, with `resize_basis="target"`. The two `-cash` sets have `cash_yield="T13W"`. The weekly one has `cadence="weekly"`, and the monthly ones have `cadence="monthly"` and `resize_cadence=None`. This file looks presets up **by id**, so the Python constant names phase 3 picks do not matter.
- Phase 4:
  - `lab survivorship` reads `$SEER_SV_STORE`.
  - `/home/miftah/seer/engine/.research-sv` has been rebuilt against the current dev store and still carries `market_series.csv`.
- **Phases 1–4 are on `origin/main` before `lab run` (Step 6).** Decided in the plan index (Decisions: "Phases 5 and 7 must land the set's code on `main` before `lab run`"): before `lab run`, rebase the feature branch onto `origin/main`, verify, and push `HEAD:main`. The shared DB's committed copy on `main` asserts that every method that ran has a file, so once this method's rows exist in the shared DB, any session that commits that DB (this one, or a parallel Sera run) would turn `main` red unless the method file and the presets it imports are already on `main`.

**Leaves alone (owned by others):**
- `sim/*`, `backtest/*`, `paper/*`, `web/lib/*` (phases 1–3)
- `commands/lab.py` and the sv store build (phase 4)
- `strategies/*` (phase 6)
- the tree-ranker method and the id after this phase's idea row (phase 7)
- every existing method file and lab row
- the test window (`lab promote` and `lab test` are never run)

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/mNNNN_near_miss_fixed_tape.py` | create | the whole method file (Step 3) |
| `/home/miftah/seer/lab/lab.sqlite` | append (via `lab` commands) | method, trials, notes, insights, idea |
| `/home/miftah/seer/web/data/lab.json` | regenerate (via `lab stage`) | snapshot of the DB |

## Implementation Steps

All commands use these variables. Export them in **every** shell; a forgotten export silently writes to the worktree's DB copy:

```bash
WT=/home/miftah/.worktrees/seer/measure-then-learn
MAIN=/home/miftah/seer
export SEER_LAB_DB=$MAIN/lab/lab.sqlite
export SEER_RESEARCH_STORE=$MAIN/engine/.research
export SEER_SV_STORE=$MAIN/engine/.research-sv
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PY=$WT/engine/.venv/bin/python
LAB="$PY -m seer_engine lab"
```

### Step 1: Preflight. The tape exists, the tools point at the right tree, and nothing is half-done

**File:** none (read-only checks)

**Change:**
1. If `$WT/engine/.venv` is missing, create it (each worktree needs its own venv):
   `python3.11 -m venv $WT/engine/.venv && $WT/engine/.venv/bin/pip install -e "$WT/engine[dev]"`.
2. `$PY -c "import seer_engine; print(seer_engine.__file__)"`. It must print a path under `$WT/engine/src`. If it prints `$MAIN`, stop and fix the venv. `lab run` checks the commit status of the method file in the directory the imported package lives in.
3. Confirm phases 1–4 landed, using the script below. Every line must print `ok`. If any line does not, stop: this phase's prerequisites are missing.
4. Run `$LAB status` and write down N, the luck bar and the test looks in the scratch file. Never type them into owner text.
5. If `$MAIN` has an unpublished lab DB (`git -C $MAIN status --porcelain -- lab/lab.sqlite web/data/lab.json` is non-empty), that is another session's work or an interrupted earlier run. Do not touch it. It is published together with this phase's rows in Step 12, which is how the redo skill repairs an interrupted batch.

**Code** (run with `$PY -`):
```python
from decimal import Decimal

from seer_engine.sim import rules as R

want = {
    "monthly-hold-frac-gotrade-tband": ("monthly", None),
    "monthly-hold-frac-gotrade-tband-cash": ("monthly", "T13W"),
    "weekly-hold-frac-gotrade-tband-cash": ("weekly", "T13W"),
}
by_id = {r.id: r for r in R.PRESETS}
print("ok" if R.TARGET_RESIZE_BAND == Decimal("0.20") else f"BAND {R.TARGET_RESIZE_BAND}: rewrite the band arithmetic in the hypothesis before Step 5")
for rid, (cadence, cash) in want.items():
    r = by_id.get(rid)
    if r is None:
        print(f"MISSING preset {rid}")
        continue
    good = (r.engine == "book" and r.fractional and r.cost_model == "gotrade" and r.resize
            and r.resize_basis == "target" and r.cash_yield == cash and r.cadence == cadence
            and r.resize_cadence is None and r.idle_symbol is None)
    print("ok" if good else f"WRONG {rid}: {r}")
    print("ok" if R.rule_owner_inputs(r) == (("cash-yield",) if cash else ()) else f"OWNER INPUTS {rid}: {R.rule_owner_inputs(r)}")
```
**Impact:** none. Reads only.

### Step 2: Check the idea is new, then reserve the id

**File:** shared DB (one `idea` row)

**Change:**
1. `$LAB seen --find "fixed tape"`, `$LAB seen --find "picking"` and `$LAB seen --find "equal-weight"`.
   - Existing keys, verified 2026-10-12: `concept:equal-weight-most-traded-members` (M0120), `concept:equal-weight-versus-cap-weight-tilt` (M0034) and two others. None is this measurement.
   - If a later session has registered a fixed-tape re-measure of these same near misses, stop and report. Never duplicate it.
2. Reserve the id. `lab idea` takes it atomically against parallel Sera sessions, which `lab next-id` alone does not:
   ```bash
   MID=$($LAB idea \
     --name "The near misses re-measured on the fixed tape, beside plain equal-weight books of the same size" \
     --family near-miss-fixed-tape \
     --source-kind variation \
     --parent M0030 \
     --source-ref "M0030-SAT100, M0007-N20-RAW, M0021-B70-RAW, M0020-W-NOSTOP; controls from M0120-EW20-ALWAYS; handover 2026-10-12 item 4; insight 211" \
     --hypothesis "Re-run the four near misses on the fixed tape (band on the holding's target, idle cash earns the T-bill) beside an ungated and a gated equal-weight 20-name control, to measure whether they won on their picks, the gate or the equal-weight shape.")
   echo "$MID"                       # e.g. M0128
   DIGITS=$(echo "$MID" | tr -d 'M') # e.g. 0128
   ```
   - If `lab idea` exits 2, read the message and act on it (see the exit-code table under Verification). Never retry blindly.
   - The runner later overwrites this row's name, family, hypothesis and source from the file (`runner.py:652-659`).
   - The family string must match the file's.

**Impact:** one `idea` row in the shared DB. Main's `test_lab_snapshot.py` is red until Step 12 stages it, which is expected and documented in the explore skill.

### Step 3: Write the method file

**File:** `$WT/engine/src/seer_engine/lab/methods/m${DIGITS}_near_miss_fixed_tape.py` (new)

**Change:** Write the file below verbatim, then fill the placeholders:
```bash
F=$WT/engine/src/seer_engine/lab/methods/m${DIGITS}_near_miss_fixed_tape.py
sed -i "s/MNNNN/$MID/g" "$F"
sed -i "s/^ADDED = date(2026, 10, 12)/ADDED = date($(date +%Y), $(date +%-m), $(date +%-d))/" "$F"
grep -c MNNNN "$F"   # must print 0
```
- The module number must equal `METHOD.id` (`m0128_…` ↔ `"M0128"`). If they differ, `discover()` raises for the whole lab.
- `ADDED` is the date the file is written.

**Code:**
```python
"""MNNNN — The near misses re-measured on the fixed tape, beside plain equal-weight books of the same size.

Source: a variation of M0030 (its 2026-10-12 amendment, SAT100) that re-measures the lab's near
misses -- M0030-SAT100, M0007-N20-RAW, M0021-B70-RAW and M0020-W-NOSTOP -- with M0120's
equal-weight 20-name book as the control; docs/plans/HANDOVER_20261012-measure-then-learn.md
section 2 item 4, and the lab's insight 211 (Sera 20261012-1842), which asked the question.

Idea: every number the lab holds for these books was measured on a tape with two known flaws.
Idle cash earned nothing, and a holding was resized only once it had drifted by 1% of the whole
account. Both are now explicit rule levers -- ``resize_basis="target"`` (20% of the holding's own
target) and ``cash_yield="T13W"`` (the 13-week T-bill yield, read the session before) -- and three
presets carry them. This method re-runs each near miss's OWN allocator and params on those
presets, so nothing about what it picks changes, and runs two plain books of the same size on the
same tape beside them. That turns Sera's question into three paired differences on one tape, one
set of deposits and one fee schedule:

    twin minus gated EW20          the picks
    gated EW20 minus ungated EW20  the SPY 200-day gate
    ungated EW20 against SPY       the equal-weight shape (SPY fed the same deposits)

Why six variants and not four twins:

    * M0030-SAT100 and M0007-N20-RAW are the SAME configuration apart from the rule set: RESIDMOM
      on RAW20 (``ResidParams(N20, scaled=False)``, which M0011 defines as "M0007-N20-RAW's
      params, verbatim" and M0030 imports). One variant covers both.
    * RAW20 runs twice, with and without the cash yield: the yield's worth is one paired
      difference, and the no-cash run is the one variant here with no owner input.
    * Two controls. Every near miss is gated by SPY's 200-day average; M0120's EW20 book is not.
      With only the ungated control, the gate's 2001-2002 and 2008 exits would be booked as
      picking. The gated control isolates them.

The gated control is the only new code. ``GATED`` wraps M0120's ``CLOCK`` (book "ew", no clock)
in ``f_factor.trend_on`` with M0007's ``TREND`` -- the same function and the same ("SPY", 200)
that RESIDMOM, the blend's calm sleeve and M0020's re-entry book read -- so the gate is the near
misses' own, and the twenty names are M0120's own. A weekly-tape EW20 control was the other
candidate for this slot; it was not chosen because the weekly twin's tape difference is already
one paired difference inside this method (the weekly twin against RAW20-CASH: same picks, same
gate), while the gate's share of the near misses' edge is measured nowhere else.

The band arithmetic, stated before the run: a 20-name equal-weight slot is 5% of the account, and
20% of 5% is 1% -- the old band. For RAW20, RAW20-CASH, the weekly twin and both controls the band
lever therefore changes nothing; only the blend (3.5% and 1.5% slots) feels it.

Presets are looked up by id in ``sim.rules.PRESETS`` rather than imported by constant name, so the
file names each rule set exactly as its trial will record it. Owner inputs are computed from the
rules (``rule_owner_inputs``), so every cash variant carries "cash-yield" honestly.

Pure: every piece reads only bars dated <= d; no clock, randomness or I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, TREND
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0020_stop_with_weekly_reentry import REENTRY, ReentryParams
from seer_engine.lab.methods.m0021_momentum_lowvol_blend import _blend
from seer_engine.lab.methods.m0120_calendar_clock import CLOCK, SCREEN, ClockParams, ClockPrepared
from seer_engine.sim.book import Target
from seer_engine.sim.rules import PRESETS, TradeRules, rule_owner_inputs
from seer_engine.strategies.allocator import BLEND
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 10, 12)


def _preset(rules_id: str) -> TradeRules:
    """The ``PRESETS`` entry whose id is ``rules_id``: the rule set exactly as a trial records it."""
    for rules in PRESETS:
        if rules.id == rules_id:
            return rules
    raise LookupError(f"sim.rules.PRESETS has no rule set {rules_id!r}")


MONTHLY_TBAND = _preset("monthly-hold-frac-gotrade-tband")
MONTHLY_TBAND_CASH = _preset("monthly-hold-frac-gotrade-tband-cash")
WEEKLY_TBAND_CASH = _preset("weekly-hold-frac-gotrade-tband-cash")

EW20 = ClockParams("ew", "none")  # M0120-EW20-ALWAYS's params, verbatim
B70_RAW = _blend("0.7", braked=False)  # M0021-B70-RAW's params, verbatim (imported as M0029 does)
W_NOSTOP = ReentryParams(RAW20, None)  # M0020-W-NOSTOP's params, verbatim


@dataclass(frozen=True, slots=True)
class GatedParams:
    """M0120's plain equal-weight book, held only while ``trend`` says the market is up."""

    book: ClockParams = EW20
    trend: tuple[str, int] = TREND

    def __post_init__(self) -> None:
        if not isinstance(self.book, ClockParams):
            raise TypeError(f"book must be ClockParams, got {type(self.book).__name__}")
        if self.book.book != "ew" or self.book.clock != "none":
            raise ValueError(f"the gated control is the plain EW book with no calendar clock, got {self.book!r}")
        if not isinstance(self.trend, tuple) or len(self.trend) != 2:
            raise TypeError(f"trend must be a (symbol, n) tuple, got {self.trend!r}")
        symbol, n = self.trend
        if not isinstance(symbol, str) or not symbol:
            raise ValueError(f"trend symbol must be a non-empty str, got {symbol!r}")
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError(f"trend n must be an int >= 1, got {n!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"trend": f"{self.trend[0]}:{self.trend[1]}"}
        for k, v in self.book.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _check(params: object) -> GatedParams:
    if not isinstance(params, GatedParams):
        raise TypeError(f"params must be GatedParams, got {type(params).__name__}")
    return params


def _gate(p: GatedParams) -> FactorParams:
    """M0120's screen with only its trend gate switched on: ``trend_on`` reads nothing else."""
    return replace(SCREEN, trend=p.trend)


class GatedEqualWeightAllocator:
    """M0120's EW book on data date d when ``trend_on`` holds on d, all cash otherwise.

    The gate is evaluated exactly as RESIDMOM evaluates it (close on d strictly above its n-day
    simple average, False when the gate symbol has no bar dated d or fewer than n bars), and the
    book is M0120's own code path, so the only difference from M0120-EW20-ALWAYS is the gate.
    """

    id = "MNNNN"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(CLOCK.lookback(p.book), p.trend[1])

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted({*CLOCK.symbols(p.book), p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return CLOCK.holds(_check(params).book)

    def uses_members(self, params: Any) -> bool:
        return CLOCK.uses_members(_check(params).book)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, _gate(p)):
            return ()
        return CLOCK.targets(history, members, data_date, held, p.book)

    def prepare(self, history: Mapping[str, History]) -> ClockPrepared:
        return CLOCK.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ClockPrepared):
            raise TypeError(f"prepared must be ClockPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        return CLOCK.targets_prepared(prepared, members, data_date, held, p.book)


GATED = GatedEqualWeightAllocator()


def _v(suffix: str, rules: TradeRules, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"MNNNN-{suffix}", family="MNNNN", rules=rules, allocator=allocator,
                     params=params, rationale=rationale, added=ADDED,
                     owner_inputs=rule_owner_inputs(rules))


METHOD = Method(
    id="MNNNN",
    name="The near misses re-measured on the fixed tape, beside plain equal-weight books of the same size",
    family="near-miss-fixed-tape",
    source_kind="variation",
    source_ref=(
        "M0030-SAT100, M0007-N20-RAW, M0021-B70-RAW, M0020-W-NOSTOP; controls from "
        "M0120-EW20-ALWAYS; docs/plans/HANDOVER_20261012-measure-then-learn.md section 2 item 4; "
        "insight 211"
    ),
    parent_id="M0030",
    hypothesis=(
        "A re-measurement, not a discovery. Every near miss here was measured on a tape that paid "
        "nothing on idle cash and resized a holding only when it drifted by 1% of the whole "
        "account. Both are fixed now as explicit levers: the band is 20% of the holding's own "
        "target, and idle cash earns the 13-week T-bill yield read the session before. All six "
        "variants run in fractional shares at Gotrade's real fee schedule, funded on the owner's "
        "plan (the opening book plus 5,000,000 IDR on the 25th of every month) against a SPY fed "
        "the identical deposits on the identical days, and every comparison below is that "
        "money-weighted pair. "
        "THE BAND ARITHMETIC, stated before the run: a 20-name equal-weight slot is 5% of the "
        "account and 20% of 5% is exactly 1%, the old band. So for RAW20-CASH, RAW20, "
        "W-NOSTOP-CASH and both controls the band fix changes nothing by construction, and RAW20 "
        "is expected to reproduce M0032-N20-RAW-FRAC-GT -- the same picks at Gotrade's fees on the "
        "old band: money-weighted 13.7% a year against 7.2% for deposit-matched SPY, a 20.6% worst "
        "fall, gains 1.98 times losses, 1,607 trades -- to within what a different starting "
        "capital can move. A material gap there is a finding about the simulator before it is "
        "anything about the method. The band bites only on the blend, whose momentum slots are "
        "3.5% of the account (band 0.7%) and calm slots 1.5% (band 0.3%): B70-CASH should trade "
        "visibly more often per name than any 20-name book here and pay for it in small-trim fees. "
        "THE CASH YIELD is where the tape moves. The gated books sit out roughly 30% of the months "
        "(M0030-SAT100 was 69% invested), and those months earn 3-5% a year before 2008 and almost "
        "nothing after it. Expected: RAW20-CASH leads RAW20 by 0.5 to 1.5 points a year of "
        "money-weighted return, almost all of it before 2008, with a worst fall within half a "
        "point of RAW20's. EW20-CASH, invested about 96% of the time, gains under 0.3 points and "
        "stays about 1.5 points a year behind deposit-matched SPY with a worst fall near 74% "
        "(M0120-EW20-ALWAYS: 5.7% against 7.2%). EW20-GATED-CASH should land near the gated "
        "most-liquid book the lab already measured (M0058-LIQ20-T: 8.1% against 7.2%, a 17.6% "
        "worst fall) plus its share of the cash interest. "
        "PICKING OR SHAPE, and the rule this method will be read by, fixed now: on this one tape, "
        "a near miss's PICKING is its money-weighted lead over deposit-matched SPY minus the gated "
        "control's lead; the GATE is the gated control's lead minus the ungated control's; the "
        "SHAPE is the ungated control's lead (negative means holding equal amounts cost money "
        "against the market). The picks are credited with an edge only if a twin beats the gated "
        "control by more than 1 point a year; otherwise the honest reading is that the near miss "
        "won on the gate and the shape. Expected: RAW20-CASH beats the gated control by 4 to 6 "
        "points a year, so the residual-momentum near misses were winning on their picks and not "
        "on their shape; the shape costs about 1.5 points a year; the gate is worth 2 to 3 points "
        "a year over the whole window, almost all of it in 2001-2002 and 2008. W-NOSTOP-CASH lands "
        "within half a point of RAW20-CASH, because with the band unchanged at 20 names the weekly "
        "re-issue still has almost nothing to do -- so insight 211's point that weekly against "
        "monthly measured nothing should hold for 20-name books even on the fixed tape. B70-CASH "
        "lands between RAW20-CASH and the gated control, its calm sleeve diluting the picks. "
        "WHAT THIS METHOD CANNOT DO is be promoted. Its line runs through M0029 and M0021, both "
        "test-failed, so the hard gate refuses it on kin whatever it scores; and every cash-yield "
        "variant carries the owner input cash-yield (Gotrade paying interest on idle dollars is "
        "not verified), which keeps it ineligible. Only RAW20 can be eligible, and it is expected "
        "to miss the 20% drawdown bar by about the 0.6 points M0032-N20-RAW-FRAC-GT did. It is a "
        "measurement, registered as a method so that it is held to this prediction; it adds one "
        "idea to the lab's count."
    ),
    expected_failure=(
        "The likeliest disappointment is that this confirms rather than changes anything: for "
        "five of the six variants the band fix is arithmetically a no-op and the cash yield is "
        "worth about a point, so the near misses land where they were, a fraction of a point "
        "either side of the 20% drawdown bar, and the method's real contribution is the control "
        "pair. Specific failures written now. (1) The picking edge may live in 1996-2002, where "
        "the dev store prices the fewest of the companies that later died: the survivorship check "
        "of 2026-10-10 took 1 to 1.4 points a year off the momentum books and pushed "
        "M0007-N20-RAW's worst fall from 19.6% to 23.5%. The picking reading must be quoted beside "
        "the check's, and if a twin's lead over the gated control falls under 1 point a year on "
        "the survivorship-check store, the answer becomes 'not clearly picking'. (2) The gated "
        "control holds the 20 most-traded members, which are the biggest companies; the near "
        "misses pick from the whole liquid pool. Part of what this method calls picking may be a "
        "tilt toward smaller members, and this method cannot separate the two. (3) The cash lever "
        "is new. If RAW20-CASH beats RAW20 by more than 2 points a year, that is a reason to audit "
        "the accrual before it is a result. (4) If W-NOSTOP-CASH differs from RAW20-CASH by more "
        "than a point, the cause is the weekly re-issue of the monthly basket at fresh prices, "
        "not the band, and must be reported that way. (5) Deposits soften every worst fall here "
        "alike; none of them may be lined up against an unfunded parent's. (6) The picking edge "
        "may be a pre-2009 edge only: if the twins trail the gated control over 2009-2015 the "
        "verdict says so first, because that is the era most like today."
    ),
    candidates=(
        _v("RAW20-CASH", MONTHLY_TBAND_CASH, RESIDMOM, RAW20,
           "The residual-momentum top 20 of M0030-SAT100 and M0007-N20-RAW, on the fixed tape with cash interest"),
        _v("RAW20", MONTHLY_TBAND, RESIDMOM, RAW20,
           "The same book with the band fix only: no cash interest and no owner input, the one variant that can be eligible"),
        _v("B70-CASH", MONTHLY_TBAND_CASH, BLEND, B70_RAW,
           "M0021-B70-RAW's 70/30 residual-momentum and calm-stock blend, on the fixed tape with cash interest"),
        _v("W-NOSTOP-CASH", WEEKLY_TBAND_CASH, REENTRY, W_NOSTOP,
           "M0020-W-NOSTOP's monthly basket re-issued weekly, on the weekly fixed tape with cash interest"),
        _v("EW20-CASH", MONTHLY_TBAND_CASH, CLOCK, EW20,
           "Control: M0120's 20 most-traded members, equal weight, no gate, on the fixed tape with cash interest"),
        _v("EW20-GATED-CASH", MONTHLY_TBAND_CASH, GATED, GatedParams(),
           "Control: the same 20-name book behind the SPY 200-day gate every near miss here reads"),
    ),
    seen_keys=(
        "concept:near-miss-fixed-tape-remeasure",
        "concept:picking-versus-equal-weight-shape",
    ),
)
```
**Impact:**
- `discover()` gains one method.
- `test_lab_methods.py` gains these cases: 1 purity, 6 smoke runs, 6 allocator contracts, and an allocator-uniqueness entry (`GATED` has id `MNNNN`; the four reused allocators are the same objects their parents use, so that test passes).
- No other file changes.

**Why `source_ref` does not carry the `redo-sera-experiments:` marker:** that marker tells the redo skill that one parent has had its realism-only twin. This method changes the tape as well as the fees and spans four parents. If it carried the marker, a later `/redo-sera-experiments M0030` would wrongly treat M0030 as already redone.

### Step 4: Verify the file before the pre-registration commit

**File:** none

**Change:** Run, in order:
1. The configuration check below. All six digests must print `NEW`, `real_cost_problem` must print `None`, and the owner inputs must be `('cash-yield',)` for the five `-CASH` variants and `()` for `RAW20`. If any digest prints `REPEATS`, stop: a repeated configuration is refused by `lab run` and must never be "fixed" by nudging a parameter.
2. `cd $WT/engine && $PY -m pytest -q tests/test_lab_methods.py`
3. `cd $WT/engine && $WT/engine/.venv/bin/ruff check src tests`

**Code** (configuration check, `$PY - "$MID"`):
```python
import sqlite3
import sys

from seer_engine.lab.method import config_digest, discover
from seer_engine.lab.real_costs import real_cost_problem

mid = sys.argv[1]
method, path = discover()[mid]
print(path)
print("real_cost_problem:", real_cost_problem(method))
conn = sqlite3.connect("file:/home/miftah/seer/lab/lab.sqlite?mode=ro", uri=True)
for c in method.all_candidates():
    d = config_digest(c)
    hit = conn.execute("SELECT candidate_id, window FROM trials WHERE config_digest = ?", (d,)).fetchall()
    r = c.rules
    print(f"{c.id:<28} {d[:12]} {'NEW' if not hit else f'REPEATS {hit}'} rules={r.id} "
          f"cadence={r.cadence} basis={r.resize_basis} cash={r.cash_yield} owner={c.owner_inputs}")
```

If the smoke test fails for the `-CASH` variants with "carries no T13W series", phase 2 Step 11
did not land: stop and report it as a phase 2 defect. Do not patch the fixture in this phase.

**Impact:** none on the lab.

### Step 5: Commit the pre-registration (the method file alone)

**File:** `engine/src/seer_engine/lab/methods/m${DIGITS}_near_miss_fixed_tape.py`

**Change:**
1. `git -C $WT status --porcelain`. Only this file may differ.
2. Full suite, DB tests included (CI fails if they skip):
   ```bash
   docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
   cd $WT/engine && $PY -m pytest -q tests && $WT/engine/.venv/bin/ruff check .
   ```
3. Commit:
   ```bash
   git -C $WT add -- engine/src/seer_engine/lab/methods/m${DIGITS}_near_miss_fixed_tape.py
   git -C $WT commit -F - <<EOF
   lab: $MID pre-registered — the near misses on the fixed tape, beside equal-weight controls

   Re-runs M0030-SAT100 / M0007-N20-RAW (one configuration), M0021-B70-RAW and
   M0020-W-NOSTOP on the target-band presets (four of them with T-bill interest on
   idle cash), next to M0120's ungated equal-weight 20 and the same book behind the
   SPY 200-day gate, to measure picking against gate against shape. Assumed: the
   20% target band equals the old 1% band for 20 equal slots, so only the blend
   feels the band; written into the hypothesis before the run.

   Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
   EOF
   ```

**Impact:** the hypothesis is frozen at this commit. From here on, the file is never edited.

### Step 6: Land phases 1–5 on `main` before the run

**File:** none (git only)

**Change:** In child-mode style (explore skill step 5):
```bash
git -C $WT fetch origin
git -C $WT rebase origin/main
cd $WT/engine && $PY -m pytest -q tests          # re-verify after the rebase (PG_TEST_URL set)
git -C $WT push origin HEAD:main
git -C $WT push origin HEAD:feature/measure-then-learn --force-with-lease
```
- If the rebase conflicts in `lab/lab.sqlite` or `web/data/lab.json`, stop. No phase in this set commits them before Step 12, so a conflict means something else is wrong.
- Landing on `main` mid-set is decided (plan index Decisions); do not pause for a merge.

**Impact:**
- `main` gains phases 1–5's commits.
- A later `lab stage` from any session no longer reds `main` with "ran but its method file is gone".
- `git status` in the method file's directory stays clean, so `lab run`'s commit check passes.

### Step 7: Run the method on the dev window

**File:** shared DB

**Change:**
```bash
cd $WT && $LAB run $MID --store $SEER_RESEARCH_STORE      # run_in_background; wait for it
```
- It prints one line per variant. A run of six variants that each read the member pool takes minutes.
- If it exits 2, read the message and use the exit-code table under Verification. The file stays committed and the method stays at status `idea`/`registered`, so fixing the cause and running again is allowed **only** when no trial was written. `lab show $MID` tells you whether one was.
- After the run, `$LAB show $MID`. Every variant must have a `funded:` line. If one does not, the runner did not fund it: stop and report, because the picking answer needs the money-weighted pair.

**Impact:**
- Six dev trials.
- Method status becomes `rejected`, or `dev-eligible` if RAW20 clears every bar.
- N rises by one for the whole lab.

### Step 8: Survivorship check, and the parents' real-fee rows

**File:** shared DB (observations only)

**Change:**
```bash
cd $WT && $LAB survivorship $MID --csv "$SCRATCH/sv-$MID.csv"     # run_in_background; report only, journals one observation
$LAB costs M0021 --candidate M0021-B70-RAW                         # report only: the blend parent at flat vs real fees
$LAB costs M0020 --candidate M0020-W-NOSTOP                        # report only: the weekly parent at flat vs real fees
```
`SCRATCH` is a fresh directory from `mktemp -d`.
- Read each variant's dev column for "reproduced" first. A dev re-run that does not match the recorded trial makes that variant's side-by-side meaningless, and the note must say so.
- `lab survivorship` refuses a store whose manifest names another dev store, or one that lacks the cash series. Either refusal means the check store is stale (the dev store moved after phase 4's rebuild). The check is never skipped (insight 208 is exactly the promise this phase exists to keep), so rebuild it offline with the runbook's command and run the check again (plan index Decisions, "A stale survivorship-check store at run time"):
  ```bash
  $PY -m seer_engine survivorship_store --build --out $MAIN/engine/.research-sv \
      --source $MAIN/engine/.research --cache $MAIN/engine/.cache/eodhd
  ```
  A second refusal after a successful rebuild is a phase 4 defect: stop and report it. Do **not** write "the check could not be done" and carry on.
- M0007-N20-RAW's real-fee row is already a recorded funded trial (M0032-N20-RAW-FRAC-GT), and M0120-EW20-ALWAYS was run at real fees, so neither needs `lab costs`.

**Impact:** up to three journal observations. No trial, no N, no look.

### Step 9: The picking / gate / shape table

**File:** `$SCRATCH/decompose.py` (scratch, not committed)

**Change:** Run `$PY $SCRATCH/decompose.py $MID`, then `$LAB status` (N, the bar, test looks), and `$LAB luck --limit 0` if you need a recorded DSR at today's N. Repeat the "picking" lines by hand from the survivorship CSV, using its funded MWR-vs-SPY columns for the survivorship-check store. The picking answer is quoted on both stores.

**Code:**
```python
"""Read-only: the picking / gate / shape decomposition of one fixed-tape method on the shared lab."""
import sqlite3
import sys

MID = sys.argv[1]
conn = sqlite3.connect("file:/home/miftah/seer/lab/lab.sqlite?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
SQL = (
    "SELECT t.candidate_id, t.start, t.rules_id, t.max_drawdown, t.mar, t.profit_factor, t.trades, "
    "t.exposure, t.failed, t.eligible, f.mwr, f.spy_tr_mwr, f.deposits_n "
    "FROM trials t JOIN trial_funding f ON f.trial_n = t.n "
    "WHERE t.window = 'dev' AND t.candidate_id = ?"
)
OWN = ("RAW20-CASH", "RAW20", "B70-CASH", "W-NOSTOP-CASH", "EW20-CASH", "EW20-GATED-CASH")
REFS = ("M0032-N20-RAW-FRAC-GT", "M0120-EW20-ALWAYS", "M0058-LIQ20-T")


def row(candidate_id):
    r = conn.execute(SQL, (candidate_id,)).fetchone()
    if r is None:
        raise SystemExit(f"no funded dev trial for {candidate_id}")
    return r


def lead(r):
    return r["mwr"] - r["spy_tr_mwr"]


def fmt(x, spec):
    return "-" if x is None else format(x, spec)


own = {s: row(f"{MID}-{s}") for s in OWN}
refs = {cid: row(cid) for cid in REFS}
print("variant | start | rules | MWR | SPY MWR (same deposits) | lead | worst fall | MAR (deposit-shaped) "
      "| PF | trades | invested | failed")
for name, r in [*own.items(), *refs.items()]:
    print(" | ".join((
        name, r["start"], r["rules_id"], fmt(r["mwr"], ".4f"), fmt(r["spy_tr_mwr"], ".4f"),
        fmt(lead(r), "+.4f"), fmt(r["max_drawdown"], ".4f"), fmt(r["mar"], ".3f"),
        fmt(r["profit_factor"], ".3f"), str(r["trades"]), fmt(r["exposure"], ".3f"), r["failed"] or "-",
    )))
gated, plain = own["EW20-GATED-CASH"], own["EW20-CASH"]
print()
for s in ("RAW20-CASH", "B70-CASH", "W-NOSTOP-CASH"):
    pick = lead(own[s]) - lead(gated)
    verdict = "PICKING credited" if pick > 0.01 else "not clearly picking"
    print(f"picking  {s:<14} lead minus gated control's lead: {pick:+.4f}  -> {verdict} (bar: +0.0100, pre-registered)")
print(f"gate     gated control minus ungated control:          {lead(gated) - lead(plain):+.4f}")
print(f"shape    ungated control's lead over SPY:              {lead(plain):+.4f}")
print(f"cash     RAW20-CASH minus RAW20 (MWR):                 {own['RAW20-CASH']['mwr'] - own['RAW20']['mwr']:+.4f}  (audit the lever if > +0.0200)")
print(f"band     RAW20 minus M0032-N20-RAW-FRAC-GT (MWR):      {own['RAW20']['mwr'] - refs['M0032-N20-RAW-FRAC-GT']['mwr']:+.4f}  (predicted ~0)")
print(f"weekly   W-NOSTOP-CASH minus RAW20-CASH (lead):        {lead(own['W-NOSTOP-CASH']) - lead(own['RAW20-CASH']):+.4f}")
print(f"tape     EW20-CASH minus M0120-EW20-ALWAYS (MWR):      {plain['mwr'] - refs['M0120-EW20-ALWAYS']['mwr']:+.4f}")
starts = {r["start"] for r in own.values()}
print(f"\nstarts: {sorted(starts)} (one start means one deposit-matched SPY for all six)")
```
**Impact:** none. Read-only.

### Step 10: The analysis note and verdict

**File:** `$SCRATCH/note-$MID.md` → `lab note`

**Change:** Write the analysis, then:
```bash
$LAB note $MID --file "$SCRATCH/note-$MID.md" --verdict "<one plain line>"
```
The verdict follows this pattern, filled from the numbers:
`On the fixed tape the momentum near misses beat a plain twenty-stock book behind the same market switch by about X points a year: they were winning on their picks, not their shape.`
If the bar was not met, use the opposite form, which states plainly that they were winning on the switch and the shape.

The note is the audit record (ids allowed), but it is written for the owner: short sentences, every number with its meaning, and jargon glossed. Required sections, in this order:
1. **What changed on the tape**, in one paragraph: interest on idle cash; the resize band now measured against each holding's own target; and why that second change does nothing for a twenty-stock equal book (20% of a 5% slot is the old 1%).
2. **The headline table**, from Step 9. Columns:
   - "what your money earned"
   - "the same deposits in SPY"
   - "lead"
   - "worst fall (deposits soften this)"
   - "gains against losses"
   - "trades"
   - "share of the time invested"
   Total and yearly returns go only in a separately labelled column, if at all ("the shape of the curve, mostly deposits"). Parents' unfunded recorded rows appear only as history, marked *unfunded*, never in the same column. The two `lab costs` reports appear as the parents' real-fee history rows, also marked *unfunded*.
3. **Picking, gate, shape**: the three numbers, the pre-registered 1-point bar, the verdict on each twin, on the dev store and on the survivorship-check store.
4. **What the cash was worth** (RAW20-CASH against RAW20), and **what the band was worth** (RAW20 against M0032; the blend's extra trades).
5. **Weekly against monthly** (W-NOSTOP-CASH against RAW20-CASH).
6. **Luck after N tries**: the N and the bar exactly as `lab status` prints them, with the funded-run caveat that deposit days look like big up days.
7. **Worst year and when the worst fall happened**: say that deposits make a fall look shallower.
8. **The survivorship check**: how much of each lead survives with the dead companies added back. Name the 2009–2015 era first.
9. **Hypothesis held? Expected failure happened?** Go item by item against the pre-registration (band no-op, cash +0.5 to +1.5, picking +4 to +6, shape about -1.5, gate +2 to +3, weekly within 0.5, and failure items 1–6).
10. **Why**: the mechanism.
11. A closing paragraph starting **`My opinion:`** that commits to a view on whether to search further in this direction, what comes next, and why.

**Impact:** analysis text and verdict on the method row.

### Step 11: The insight and the next idea

**File:** shared DB

**Change:**
```bash
$LAB insight --kind observation --method $MID \
  --title "<the answer, in plain words, e.g. 'Our best near misses were winning on their picks, not on holding equal amounts'>" \
  --file "$SCRATCH/insight-$MID.md"
```
The insight body is read by a curious non-trader:
- No ids, digests, code, file paths or backticks.
- Methods are named by what they do ("the momentum book", "the plain twenty-stock book", "the same plain book that steps aside when the market falls below its 200-day average").
- No bar or limit is written as a number. Say "inside the limit" or "short of the bar".

It must state, in this order:
1. The answer to "picking or shape" in one sentence.
2. The three numbers as points a year with their meaning (what the picks added, what the market switch added, what equal amounts cost against simply holding the market).
3. Whether that survives adding back the companies that died.
4. What interest on idle cash changed.
5. The finding that the new rebalancing threshold changes nothing for a twenty-stock book, and where it would matter (fifty-stock books).
6. What to do about it.

Then queue at least one next idea, chosen from the result:
- If picking was credited: `--name "The residual-momentum picks in a fifty-stock book on the fixed tape" --family near-miss-fixed-tape --source-kind variation --parent $MID`. This is where the target band actually bites, and Sera's queued shape work aims there.
- If picking was not credited: `--name "The plain twenty-stock book sized by how heavily each name trades, behind the market switch" --family near-miss-fixed-tape --source-kind variation --parent $MID`. This is Sera's open question of whether trading-volume sizing repairs the shape.

Check `lab seen --find` first. The hypothesis is one plain paragraph drawn from this result. **This idea row takes the id after `$MID`**, and phase 7 must take its own id from `lab next-id` at its run time, as planned.

**Impact:** one insight, one idea row.

### Step 12: Stage and publish

**File:** `$MAIN/lab/lab.sqlite`, `$MAIN/web/data/lab.json`

**Change:** `lab stage` writes beside the database it points at, which is the main checkout. Commit there, by explicit pathspec only:
```bash
cd $WT && $LAB stage                                   # prints: staged .../lab/lab.sqlite and .../web/data/lab.json
git -C $MAIN commit -F - -- lab/lab.sqlite web/data/lab.json <<EOF
lab: $MID rejected (<plain reason, e.g. the momentum near misses won on their picks, but still fall just past the limit>)

Six variants on the fixed tape: <one line of the picking / gate / shape numbers>.
Survivorship check: <one line>. N and test looks as lab status printed them.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git -C $MAIN -c rebase.autoStash=true pull --rebase origin main
git -C $MAIN push origin main
cd $MAIN/engine && $MAIN/engine/.venv/bin/python -m pytest -q tests     # main now has phases 1-5; must be green
```
- If the status is `dev-eligible` (RAW20 cleared every bar), the subject is `lab: $MID dev-eligible — …`. **Do not promote**: the kin gate refuses it, and this set never touches the test window.
- Never `git add -A`. Never `checkout`, `restore` or `stash` `lab/lab.sqlite` by hand.
- Then bring the worktree level for phase 7:
  `git -C $WT fetch origin && git -C $WT rebase origin/main && git -C $WT push origin HEAD:feature/measure-then-learn --force-with-lease`.

**Impact:**
- `main` carries the method's rows and the snapshot.
- Vercel redeploys `/sera`.
- CI's lab.json/lab.sqlite agreement holds.

## Verification

**Build:** `cd $WT/engine && $PY -c "from seer_engine.lab.method import discover; m,_ = discover()['$MID']; print(len(m.candidates))"` prints `6`.

**Tests:**
- Before the pre-registration: `cd $WT/engine && $PY -m pytest -q tests/test_lab_methods.py && $WT/engine/.venv/bin/ruff check src tests`.
- Then the full suite with `PG_TEST_URL` set (Step 5.2).
- After staging: `cd $MAIN/engine && $MAIN/engine/.venv/bin/python -m pytest -q tests` (includes `test_lab_snapshot.py`, `test_lab_methods.py` frozen-sha and digest checks, and `test_cost_model_pins.py`).

**Manual check:**
- `$LAB show $MID` shows six dev trials, each with a `funded:` line.
- `$LAB status` shows the method, and N went up by exactly one.
- Test looks are unchanged.
- The note's verdict and the insight read without ids.
- Optional: `run-the-web-app` on `/sera/methods/$MID` after deploy.

**Exit criteria:**
- `main` holds the committed method file.
- The shared DB holds six dev trials for `$MID`, a survivorship observation, an analysis note whose last paragraph begins `My opinion:`, and a plain-words observation insight stating the picking / gate / shape answer.
- One queued idea.
- `lab/lab.sqlite` and `web/data/lab.json` are committed together on `main`.
- The full engine suite is green on `main`.
- No test-window trial exists for `$MID`.

**Exit codes (any `lab` command).** 0 = ok, 1 = error, 2 = the lab's rules refused. On a 2, read the message, act on it, and never retry blindly:

| Message contains | Meaning | Action |
|---|---|---|
| `Commit the method file first` | the file is untracked, dirty or staged-only, or the venv imports another tree | Step 1.2 and Step 5. Never pass `require_commit=False` |
| `repeats …, which already ran` | a digest collision | stop. Never nudge a parameter. Report it: the Step 4 check should have caught it |
| `would run at the lab's old flat cost` | a preset is not `cost_model="gotrade"` | a phase 3 defect: stop and report |
| `is already rejected/dev-eligible` | it has run already | nothing to do: continue at Step 8 |
| a store / prices / D10 refusal | the dev store is not the benchmark's | pull it with `sync-research-store`; never rebuild casually |
| a missing `T13W` / series refusal | a phase 2 store check | `SEER_RESEARCH_STORE` must be the main checkout's dev store (it has the series) |
| `survivorship` manifest / purpose refusal | the sv store is stale or wrong | a phase 4 defect: stop and report |

## Handoffs

- **Phase 1.** `TARGET_RESIZE_BAND = 0.20` (kept by the reconciler; plan index Decisions) equals the old band exactly for every 20-name equal-weight book (0.20 × 5% = 1%). So the band half of the "fixed tape" is invisible to four of the five near-miss configurations and to the weekly-vs-monthly question insight 211 raised. This phase writes that into its hypothesis rather than tuning around it. Step 1's check is a guard only: it prints `ok` for the decided constant.
- **Phase 2.** The smoke-fixture fix (`labkit.SMOKE_T13W`, attached by `test_lab_methods` for cash-yield candidates) is phase 2 Step 11's (reconciled); this phase changes no fixture.
- **Phase 4.** The survivorship-check store keeps `market_series.csv` through its rebuild; phase 4 Step 7.6 verifies it is byte-identical to the dev store's.
- **Phase 7.** This phase's idea row (Step 11) consumes the id after `$MID`. Phase 7 takes its id from `lab next-id` at its own run time, after Step 12 has landed and the worktree has been rebased onto `main`.
- **Orchestrator.** Step 6 lands phases 1–5 on `main` mid-set, as decided in the plan index; phase 7 depends on this landing.
- **Not done here (out of scope):** promotion of anything; a fifty-name fixed-tape book (queued as an idea if picking is credited); the trading-volume-sized control (queued if picking is not credited).

## Rollback

- **Before Step 6:** `git -C $WT reset --soft HEAD~1` (or revert the pre-registration commit), delete the file, and `$LAB drop $MID --why "withdrawn before it ran: <reason>"`. The idea row stays as a dropped record. Ids are never reused.
- **After Step 6 but before Step 7:** revert the pre-registration on `main` with a normal `git revert` commit and `lab drop` the id, as above.
- **After Step 7:** no rollback. Trials and insights are append-only by schema triggers, and the file is frozen by `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`. A mistaken run is explained in a further `lab note`, never deleted or re-run. A different configuration is a new variation method with its own pre-registration.

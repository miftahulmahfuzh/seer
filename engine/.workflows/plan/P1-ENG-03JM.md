> Adopted from `MEASURE_THEN_LEARN_PLAN.md` phase 3. Source: `.workflows/plan/measure-then-learn/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: Fixed-tape presets and the web mirror

**Plan set:** `MEASURE_THEN_LEARN_PLAN.md`
**Analysis:** `20261012-205553-M7T1_code_analyzer.md`
**Satisfies:** R1, R2. Lab methods and the web can name a rule set whose resize band is measured against the holding's own target (R1), with or without idle cash earning the T-bill yield (R2).
**Depends on:** Phase 1 (`resize_basis`, `TARGET_RESIZE_BAND`), Phase 2 (`cash_yield`, owner input `cash-yield`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/sim` (presets), `web/lib` (mirror)

---

## Goal

After this phase `sim.rules.PRESETS` ends with three new rule sets built on the fixed tape:
`monthly-hold-frac-gotrade-tband` (target band), `monthly-hold-frac-gotrade-tband-cash` (target
band plus T-bill cash) and `weekly-hold-frac-gotrade-tband-cash` (the weekly arm of the same
tape). Phases 5 and 7 can import them by name. The web's hand mirrors know them:
`RESIZING_RULES` includes them, the new `TARGET_BAND_RULES` and `TARGET_RESIZE_BAND` mirror the
engine, and the reminder and size-cell gap tests use the target band for those rules. The engine
mirror test guards both new mirrors. No existing preset, pinned digest, roster row or simulator
line changes.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `sim.rules.MONTHLY_HOLD_FRAC_GOTRADE_TBAND` (id `monthly-hold-frac-gotrade-tband`) = `replace(MONTHLY_HOLD_FRAC_GOTRADE, id=..., resize_basis="target")` (`engine/src/seer_engine/sim/rules.py`)
- `sim.rules.MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH` (id `monthly-hold-frac-gotrade-tband-cash`) = `replace(MONTHLY_HOLD_FRAC_GOTRADE_TBAND, id=..., cash_yield="T13W")`
- `sim.rules.WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH` (id `weekly-hold-frac-gotrade-tband-cash`) = `replace(WEEKLY_HOLD, id=..., fractional=True, cost_model="gotrade", resize_basis="target", cash_yield="T13W")`
- `PRESETS` grows from 16 to 19 entries. The three are appended **at the end, in that order**: `PRESETS[16]`, `PRESETS[17]`, `PRESETS[18]`.
- web `lib/cadence.ts`: `export const TARGET_RESIZE_BAND = 0.2`, `export const TARGET_BAND_RULES: readonly string[]`, `export type ResizeBasis = 'equity' | 'target'`, `export function resizeBasisOf(rulesId)`
- web `lib/sean/reminders.ts`: `ReminderInput.resizeBasis: ResizeBasis` (new **required** field)
- `engine/tests/test_sim_rules_fixed_tape.py` (new test file)

**Signature changes (web, all backward compatible through defaults except `ReminderInput`):**
- `sizeChange(weight, equity, heldUsd)` -> `sizeChange(weight, equity, heldUsd, basis: ResizeBasis = 'equity')`
- `orderSizeChange(weight, equity, symbol, held)` -> `orderSizeChange(weight, equity, symbol, held, basis: ResizeBasis = 'equity')`
- `sizeTip(c)` -> `sizeTip(c, basis: ResizeBasis = 'equity')`
- `ReminderInput` gains the required `resizeBasis`. The only non-test constructor, `lib/sean/planData.ts:189`, is updated.

**Not exported from `seer_engine.sim`:** the three new presets are importable from
`seer_engine.sim.rules` only. This is the same as `MONTHLY_HOLD_FRAC_GOTRADE` today, and it keeps
`sim/__init__.py` (edited by phases 1 and 2) out of this phase.

**Requires (from earlier phases):**
- Phase 1: `TradeRules.resize_basis` field (`"equity"` default, `"target"` accepted for book rule sets with `resize=True`); `sim.rules.TARGET_RESIZE_BAND = Decimal("0.20")`; `LEVERS_SINCE_PINS["resize_basis"] = "equity"`; `describe_rules` still returns **12 lines**, with the Rebalance line changed for the target basis.
- Phase 2: `TradeRules.cash_yield` field (`None` default, `"T13W"` accepted); `LEVERS_SINCE_PINS["cash_yield"] = None`; `rule_owner_inputs` adds `"cash-yield"` when `cash_yield is not None`; `describe_rules` still returns **12 lines**, with the Idle cash line changed. `paper.roster.rules_for(id)` still returns a preset by id: phase 2 refuses cash-yield rules in `promote._check_rules` (NotPromotable, message contains "interest on idle cash") and in `paper.book.decide_book`/`settle_book`, never in the lookup or in `_book_rules`.
- Phase 1's `test_resize_basis_defaults_to_equity_everywhere` and phase 2's `test_cash_yield_defaults_to_none_and_is_a_pinned_no_op` assert only over `PRESETS[:16]`, and phase 2's `test_the_pins_cover_every_book_preset_that_predates_the_lever` excludes presets with either lever set, so appending the three presets here needs no edit to `test_resize_basis_pins.py` or `test_cash_yield.py` (reconciled).
- Neither phase appends to `PRESETS` and neither changes an existing preset.

**Leaves alone (owned by others):** `sim/book.py` and the band helper (Phase 1); `step_book` cash accrual, `book_runner`, the paper refusal (Phase 2); `paper/roster.py SEED_ROWS` and the PINS (invariant 3, nobody); `sim/__init__.py` (Phases 1 and 2); `web/app/(app)/positions/page.tsx` (see Handoffs); `commands/lab.py`, the skills and the sv store (Phase 4); lab method files and lab data (Phases 5 and 7).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/rules.py` | modify | three new presets after `DESIGN_V0_GOTRADE` (:192 today), appended to `PRESETS` (:194-211 today) |
| `engine/tests/test_sim_rules.py` | modify | `test_preset_ids_are_unique_and_in_order` (:94-116) lists the three ids; `test_owner_inputs_of_the_presets` (:251-254) expects `cash-yield` |
| `engine/tests/test_lab_costs.py` | modify | `PRESETS[-2:]` (:306) becomes the positional slice `PRESETS[14:16]` |
| `engine/tests/test_cost_model_pins.py` | modify | the non-flat id list (:86-90) gains the three ids |
| `engine/tests/test_sim_rules_fixed_tape.py` | create | pins the three presets: values, order, canonical form, owner inputs, promote mapping, descriptions |
| `engine/tests/test_sean_mirrors.py` | modify | import (:40), `GUARDED` (:47-52), two new mirror tests, `test_every_mirror_is_covered` (:130) |
| `web/lib/cadence.ts` | modify | `CADENCE` (:34-51) gains the three ids; `TARGET_RESIZE_BAND`, `TARGET_BAND_RULES`, `ResizeBasis`, `resizeBasisOf` (after :73); `sizeChange` (:88), `orderSizeChange` (:104), `sizeTip` (:120) take the basis |
| `web/lib/cadence.test.ts` | modify | imports (:2-5); new tests for the target band and the cadences |
| `web/lib/sean/reminders.ts` | modify | header rule (:13-15), import (:33), `RESIZING_RULES` (:64-76), `ReminderInput` (:130-137), the band at :324-326 |
| `web/lib/sean/reminders.test.ts` | modify | `input()` helper (:31-36) sets `resizeBasis: 'equity'`; `resizes` test (:449-457); new target-band describe block |
| `web/lib/sean/planData.ts` | modify | import (:11-14), pass `resizeBasis: resizeBasisOf(l.rulesId)` (:190) |

Line numbers are those on `origin/main @ 5faa3cb`. In `rules.py` and `test_sim_rules.py`, phases 1
and 2 shift them by a few lines. Each step names the textual anchor it lands on.

## Implementation Steps

### Step 1: The three presets
**File:** `engine/src/seer_engine/sim/rules.py`. Insert right after the `DESIGN_V0_GOTRADE = ...`
line (:192 today) and before `PRESETS: tuple[TradeRules, ...] = (` (:194 today).
**Change:** add three module-level presets with WHY comments, in the style of the presets above them.
**Code:**
```python
# The fixed measuring tape (handover 2026-10-12, "measure then learn", Step 0). Under RESIZE_BAND a
# held name is traded back only when its gap reaches 1% of the WHOLE account, so in a 20-50 name
# book it must drift 50-100% of its own target before anything trades, and "resize" was close to a
# no-op. This preset measures the band against the holding's own target instead
# (resize_basis="target", TARGET_RESIZE_BAND = 20% of weight x equity). Every other lever is
# monthly-hold-frac-gotrade's, so a twin built on it isolates the tape. A new id, never an edit:
# every recorded trial and pinned paper spec stays on the old presets byte for byte. No roster
# entry uses it (live paper is unchanged), but it carries no owner input and is promotable, so the
# web mirrors know it (cadence.ts TARGET_BAND_RULES, reminders.ts RESIZING_RULES).
MONTHLY_HOLD_FRAC_GOTRADE_TBAND = replace(
    MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-tband", resize_basis="target"
)
# The same tape with idle cash earning the 13-week T-bill yield (cash_yield="T13W", read
# point-in-time from the store's market series). Cash that waits for the month-start rotation, and
# the money a rule steps aside with, used to earn nothing. It raises the owner input "cash-yield"
# (that Gotrade pays interest on idle dollars is not verified) and paper refuses it, so it is a
# lab measurement: what a method looks like when its waiting money is credited as a real account
# could credit it.
MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH = replace(
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND, id="monthly-hold-frac-gotrade-tband-cash", cash_yield="T13W"
)
# The weekly arm on the fixed tape: weekly-hold in fractional shares at Gotrade's real fees, target
# band, T-bill cash. Real-fee weekly books so far were one-off rule sets inside method files
# (weekly-hold-frac-gotrade in M0063, M0064, M0076, M0085), not presets. Under the old band
# weekly-against-monthly measured little, because a weekly resize almost never cleared 1% of
# equity; the near-miss twins (M0020-W-NOSTOP ran weekly) need a weekly arm on the same tape.
WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH = replace(
    WEEKLY_HOLD,
    id="weekly-hold-frac-gotrade-tband-cash",
    fractional=True,
    cost_model="gotrade",
    resize_basis="target",
    cash_yield="T13W",
)
```
**Impact:** the module only gains names. Each `replace` runs phase 1's and phase 2's `__post_init__` validation at import time, so a mistake in either lever's validation shows up as an import error at once.

### Step 2: Append them to `PRESETS`
**File:** `engine/src/seer_engine/sim/rules.py`, the `PRESETS` tuple (:194-211 today).
**Change:** append the three after `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE`. Do not reorder any existing entry: `PRESETS[12]`, `PRESETS[13]` and `PRESETS[:13]` are positionally asserted.
**Code (the whole tuple after the change):**
```python
PRESETS: tuple[TradeRules, ...] = (
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_HOLD_TBILL,
    WEEKLY_HOLD,
    DAILY_SWITCH,
    DAILY_SWITCH_TBILL,
    SWING_T10,
    SWING_T20,
    SWING_T20_OPEN,
    MONTHLY_RANK_WEEKLY_RESIZE,
    MONTHLY_RANK_WEEKLY_RESIZE_TBILL,
    MONTHLY_HOLD_FRAC,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC,
    DESIGN_V0_GOTRADE,
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH,
    WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH,
)
```
**Impact:**
- `paper.roster._PRESETS` (roster.py:704) and `roster.rules_for` resolve the three ids. `SEED_ROWS` is untouched, so no roster row and no pinned spec digest moves.
- `promote.fractional_twin` (promote.py:145) scans `PRESETS`. All three new presets are fractional, and none matches a non-fractional preset on every lever except `id`/`fractional` (they differ in `cost_model`, `resize_basis` and `cash_yield`), so no existing `--fractional` mapping changes. Step 7 pins this.
- The tests that enumerate `PRESETS` and need updating are steps 3-5. The rest pass unchanged:
  - `test_sim_rules.test_preset_values_are_pinned` (all book, dividends on, default cost_rate; `PRESETS[:13]` flat)
  - `test_rules_are_frozen_and_hashable`
  - `test_resize_cadence_defaults_to_none...` (no new `resize_cadence`)
  - `PRESETS[12]` / `PRESETS[13]`
  - `describe_rules` length 12 (see Requires)
  - `test_paper_kickoff.test_without_a_resize_cadence_the_kickoff_test_is_unchanged` (pure cadence logic)
  - `test_registry.test_rules_are_registry_presets_never_v0_book` (REGISTRY unchanged)
  - `test_cost_model_pins.test_flat_is_absent_from_every_canonical_form`'s loop (the new presets are gotrade and `rules_dict` names it)

### Step 3: `test_sim_rules.py`: the id list and the owner inputs
**File:** `engine/tests/test_sim_rules.py`. `test_preset_ids_are_unique_and_in_order` (:94-116 today) and `test_owner_inputs_of_the_presets` (:251-254 today).
**Change:** the id list gains the three ids in order. The owner-inputs test also expects `cash-yield` for a preset with `cash_yield`. Phases 1 and 2 do not edit either function (they edit only `test_a_lever_added_after_the_pins_is_left_out_of_canonical_text_at_its_default` and append at the end of the file), so both are quoted here as they stand on `5faa3cb`.
**Code:**
```python
def test_preset_ids_are_unique_and_in_order():
    ids = [r.id for r in PRESETS]
    assert ids == [
        "design-v0",
        "monthly-hold",
        "monthly-hold-tbill",
        "weekly-hold",
        "daily-switch",
        "daily-switch-tbill",
        "swing-t10",
        "swing-t20",
        "swing-t20-open",
        "monthly-rank-weekly-resize",
        "monthly-rank-weekly-resize-tbill",
        "monthly-hold-frac",
        "monthly-rank-weekly-resize-frac",
        "design-v0-gotrade",
        "monthly-hold-frac-gotrade",
        "monthly-rank-weekly-resize-frac-gotrade",
        "monthly-hold-frac-gotrade-tband",
        "monthly-hold-frac-gotrade-tband-cash",
        "weekly-hold-frac-gotrade-tband-cash",
    ]
    assert len(set(ids)) == len(ids)
```
```python
def test_owner_inputs_of_the_presets():
    for r in PRESETS:
        expected: set[str] = set()
        if r.idle_symbol == "BIL":
            expected.add("etf:BIL")
        if r.cash_yield is not None:
            expected.add("cash-yield")
        assert rule_owner_inputs(r) == tuple(sorted(expected)), r.id
    assert rule_owner_inputs(V0_BOOK) == ()
```
**Impact:** test-only.

### Step 4: `test_lab_costs.py`: `PRESETS[-2:]` becomes positional
**File:** `engine/tests/test_lab_costs.py:306`.
**Change:** the assertion pinned the two real-fee book presets as the last two. With three presets appended they sit at 14 and 15. Slice by position so the assertion keeps its meaning: the real-fee pair keeps its place.
**Code (replaces line 306 only):**
```python
    assert PRESETS[14:16] == (MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE)
```
**Impact:** test-only.

### Step 5: `test_cost_model_pins.py`: the non-flat id list
**File:** `engine/tests/test_cost_model_pins.py:86-90`.
**Change:** the list of presets that name a cost model gains the three new ids, which are all `cost_model="gotrade"`.
**Code (replaces the final assertion of `test_flat_is_absent_from_every_canonical_form`):**
```python
    assert [r.id for r in PRESETS if r.cost_model != "flat"] == [
        "design-v0-gotrade",
        "monthly-hold-frac-gotrade",
        "monthly-rank-weekly-resize-frac-gotrade",
        "monthly-hold-frac-gotrade-tband",
        "monthly-hold-frac-gotrade-tband-cash",
        "weekly-hold-frac-gotrade-tband-cash",
    ]
```
**Impact:** test-only.

### Step 6: Engine mirror guard for the two new web mirrors
**File:** `engine/tests/test_sean_mirrors.py`
**Change:**
1. Module docstring, first paragraph (:3-5): the list of retyped values now names the target band and its rule sets.
2. Import (:40) gains `TARGET_RESIZE_BAND`.
3. `GUARDED` (:47-52) gains two entries, both in `CADENCE`.
4. Two new tests after `test_resizing_rules_are_exactly_the_book_presets_that_resize` (:92-104).
5. `test_every_mirror_is_covered` (:128-132) asserts the six-name set.

**Code (docstring lines 3-5 replacement):**
```python
``web/lib/sean`` runs in the browser and on the Next server, so a handful of engine values are
retyped there: the owner's contribution schedule, the resize band, the rule sets that resize, the
target band and the rule sets measured against it, and the fallback USD/IDR rate. Each carries a
comment naming its Python twin -- and until this file,
```
**Code (import, line 40):**
```python
from seer_engine.sim.rules import PRESETS, RESIZE_BAND, TARGET_RESIZE_BAND
```
**Code (`GUARDED`):**
```python
GUARDED: dict[str, str] = {
    "RESIZE_BAND": CADENCE,
    "TARGET_RESIZE_BAND": CADENCE,
    "TARGET_BAND_RULES": CADENCE,
    "RESIZING_RULES": REMINDERS,
    "OWNER_MONTHLY": CASH,
    "OWNER_USD_IDR": CASH,
}
```
**Code (new tests, inserted after the `RESIZING_RULES` test):**
```python
def test_target_resize_band_matches_the_engine():
    """``cadence.TARGET_RESIZE_BAND`` sizes the target-basis band on the reminders and the size cell."""
    assert _const(_src(CADENCE), "TARGET_RESIZE_BAND", CADENCE) == TARGET_RESIZE_BAND


def test_target_band_rules_are_exactly_the_presets_on_the_target_basis():
    """``cadence.resizeBasisOf`` decides which band a held pick is measured against.

    Miss a preset and the page asks for adds and trims a fifth-of-target band would never make;
    invent one and it hides trades the 1%-of-equity band does make. The set is derived, never typed.
    """
    derived = {r.id for r in PRESETS if r.resize_basis == "target"}
    assert derived, "no preset is on the target basis; this guard would pass by finding nothing"
    mirrored = _string_array(_src(CADENCE), "TARGET_BAND_RULES", CADENCE)
    assert len(mirrored) == len(set(mirrored)), "TARGET_BAND_RULES has a duplicate"
    assert set(mirrored) == derived, (
        f"TARGET_BAND_RULES drifted: only in TS {sorted(set(mirrored) - derived)}, "
        f"only in the engine {sorted(derived - set(mirrored))}"
    )
```
**Code (`test_every_mirror_is_covered`):**
```python
def test_every_mirror_is_covered():
    """The guarded set has not quietly shrunk, and each name is still in the file claimed."""
    assert set(GUARDED) == {
        "RESIZE_BAND",
        "TARGET_RESIZE_BAND",
        "TARGET_BAND_RULES",
        "RESIZING_RULES",
        "OWNER_MONTHLY",
        "OWNER_USD_IDR",
    }
    for name, rel in GUARDED.items():
        assert f"export const {name}" in _src(rel), f"{name} is no longer exported from {rel}"
```
**Impact:** the existing `test_resizing_rules_are_exactly_the_book_presets_that_resize` now
derives three more ids (all three new presets are `engine="book"`, `resize=True`).
It fails until step 9 adds them to `RESIZING_RULES`, so steps 2, 6 and 9 must land in one commit.
`_const`'s regex for `RESIZE_BAND` does not match `TARGET_RESIZE_BAND`, because the text
`export const RESIZE_BAND` does not occur inside `export const TARGET_RESIZE_BAND`.
`Decimal("0.2") == Decimal("0.20")` holds.

### Step 7: New engine test file pinning the presets
**File:** `engine/tests/test_sim_rules_fixed_tape.py` (create). It is a separate file so it does
not collide with phase 1/2 edits to `test_sim_rules.py`.
**Code:**
```python
"""The fixed-tape presets (measure-then-learn, phase 3).

Three rule sets carry the two Step 0 fixes: the resize band measured against the holding's own
target (``resize_basis="target"``) and idle cash earning the 13-week T-bill yield
(``cash_yield="T13W"``). They are new ids appended to ``PRESETS``, never edits, so these tests pin
two things: each preset is exactly its base plus the named levers, and nothing that was already
pinned (the old presets' canonical form, the promote mapping, the paper roster) moved.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from seer_engine.commands import promote
from seer_engine.paper import roster
from seer_engine.sim.rules import (
    LEVERS_SINCE_PINS,
    MONTHLY_HOLD,
    MONTHLY_HOLD_FRAC,
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH,
    PRESETS,
    WEEKLY_HOLD,
    WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH,
    describe_rules,
    rule_owner_inputs,
)

TAPE = (
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
    MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH,
    WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH,
)


def test_each_preset_is_its_base_plus_the_named_levers():
    assert MONTHLY_HOLD_FRAC_GOTRADE_TBAND == replace(
        MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-tband", resize_basis="target"
    )
    assert MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH == replace(
        MONTHLY_HOLD_FRAC_GOTRADE, id="monthly-hold-frac-gotrade-tband-cash", resize_basis="target",
        cash_yield="T13W",
    )
    assert WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH == replace(
        WEEKLY_HOLD, id="weekly-hold-frac-gotrade-tband-cash", fractional=True, cost_model="gotrade",
        resize_basis="target", cash_yield="T13W",
    )


def test_the_shared_levers():
    for r in TAPE:
        assert r.engine == "book", r.id
        assert r.resize is True and r.resize_cadence is None, r.id
        assert r.fractional is True and r.cost_model == "gotrade", r.id
        assert r.resize_basis == "target", r.id
        assert r.entry == "open_limit" and r.idle_symbol is None and r.dividends is True, r.id
    assert MONTHLY_HOLD_FRAC_GOTRADE_TBAND.cash_yield is None
    assert MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH.cash_yield == "T13W"
    assert WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH.cash_yield == "T13W"
    assert [r.cadence for r in TAPE] == ["monthly", "monthly", "weekly"]


def test_they_are_appended_last_in_order_and_nothing_else_moved():
    assert PRESETS[16:] == TAPE
    assert len(PRESETS) == 19
    assert PRESETS[14] is MONTHLY_HOLD_FRAC_GOTRADE
    assert [r.resize_basis for r in PRESETS[:16]] == ["equity"] * 16
    assert [r.cash_yield for r in PRESETS[:16]] == [None] * 16


def test_owner_inputs():
    # The target band is pure simulator arithmetic: nothing for the owner to verify.
    assert rule_owner_inputs(MONTHLY_HOLD_FRAC_GOTRADE_TBAND) == ()
    # Interest on idle dollars at Gotrade is not verified.
    assert rule_owner_inputs(MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH) == ("cash-yield",)
    assert rule_owner_inputs(WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH) == ("cash-yield",)


def test_canonical_form_names_the_new_levers_and_the_old_presets_still_omit_them():
    assert set(LEVERS_SINCE_PINS) >= {"resize_basis", "cash_yield"}
    for r in PRESETS[:16]:
        d = roster.rules_dict(r)
        assert "resize_basis" not in d and "cash_yield" not in d, r.id
    tband = roster.rules_dict(MONTHLY_HOLD_FRAC_GOTRADE_TBAND)
    assert tband["resize_basis"] == "target" and "cash_yield" not in tband
    for r in (MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH, WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH):
        d = roster.rules_dict(r)
        assert d["resize_basis"] == "target" and d["cash_yield"] == "T13W", r.id
    base = roster.rules_dict(MONTHLY_HOLD_FRAC_GOTRADE)
    assert {k: v for k, v in tband.items() if k not in ("id", "resize_basis")} == {
        k: v for k, v in base.items() if k != "id"
    }


def test_the_cash_free_preset_resolves_on_the_roster_and_the_promote_mapping_is_unchanged():
    assert roster.rules_for("monthly-hold-frac-gotrade-tband") is MONTHLY_HOLD_FRAC_GOTRADE_TBAND
    # a fractional preset is its own twin
    for r in TAPE:
        assert promote.fractional_twin(r) is r, r.id
    # the old whole-share presets still map where they did; none landed on a fixed-tape preset
    assert promote.fractional_twin(MONTHLY_HOLD) is MONTHLY_HOLD_FRAC
    with pytest.raises(promote.NotPromotable, match="no fractional preset"):
        promote.fractional_twin(WEEKLY_HOLD)


def test_promote_takes_the_band_preset_and_refuses_the_cash_presets():
    # phase 2's refusal fires for the real preset ids, not only for one-off test rule sets
    promote._check_rules(MONTHLY_HOLD_FRAC_GOTRADE_TBAND)
    for r in (MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH, WEEKLY_HOLD_FRAC_GOTRADE_TBAND_CASH):
        with pytest.raises(promote.NotPromotable, match="interest on idle cash"):
            promote._check_rules(r)


def test_descriptions_differ_from_the_base_and_keep_twelve_lines():
    base = describe_rules(MONTHLY_HOLD_FRAC_GOTRADE)
    tband = describe_rules(MONTHLY_HOLD_FRAC_GOTRADE_TBAND)
    cash = describe_rules(MONTHLY_HOLD_FRAC_GOTRADE_TBAND_CASH)
    assert len(tband) == len(cash) == len(base) == 12
    # target band: only the rule-set name and the Rebalance line differ from the base
    assert [i for i in range(12) if tband[i] != base[i]] == [0, 7]
    # plus cash: and the Idle cash line
    assert [i for i in range(12) if cash[i] != tband[i]] == [0, 10]
```
**Impact:** test-only. The line indices in the last test follow `describe_rules`' field order:
0 Rule set, 1 Engine, 2 Decisions, 3 Re-scaling, 4 Entry, 5 Positions, 6 Time stop, 7 Rebalance,
8 Shares, 9 Dividends, 10 Idle cash, 11 Costs. They match `test_sim_rules.py:320-328` (index 11 is
Costs, index 6 is Time stop). If phase 1 or 2 changed the line count, which their plans must not
do (see Requires), adjust these indices and `test_sim_rules.py:328` together.

### Step 8: `web/lib/cadence.ts`: the target band mirror and the basis
**File:** `web/lib/cadence.ts`
**Change 8a:** the `CADENCE` table (:34-51) learns the three ids, so `cadenceOf` and `sellsWhen` answer for them instead of `unknown`.
**Code (whole table):**
```ts
const CADENCE: Record<string, Cadence> = {
  'design-v0': 'daily',
  'design-v0-gotrade': 'daily',
  'daily-switch': 'daily',
  'daily-switch-tbill': 'daily',
  'swing-t10': 'daily',
  'swing-t20': 'daily',
  'swing-t20-open': 'daily',
  'weekly-hold': 'weekly',
  'weekly-hold-frac-gotrade-tband-cash': 'weekly',
  'monthly-hold': 'monthly',
  'monthly-hold-tbill': 'monthly',
  'monthly-hold-frac': 'monthly',
  'monthly-hold-frac-gotrade': 'monthly',
  'monthly-hold-frac-gotrade-tband': 'monthly',
  'monthly-hold-frac-gotrade-tband-cash': 'monthly',
  'monthly-rank-weekly-resize': 'monthly-weekly',
  'monthly-rank-weekly-resize-tbill': 'monthly-weekly',
  'monthly-rank-weekly-resize-frac': 'monthly-weekly',
  'monthly-rank-weekly-resize-frac-gotrade': 'monthly-weekly',
};
```
**Change 8b:** replace lines 68-109 (the `RESIZE_BAND` doc and constant through `orderSizeChange`) with the block below. It keeps `RESIZE_BAND = 0.01` unchanged.
**Code:**
```ts
/**
 * Mirror of the engine's `RESIZE_BAND = Decimal("0.01")` (engine/src/seer_engine/sim/rules.py):
 * on the equity basis (every rule set not in TARGET_BAND_RULES) a held position is only traded
 * back to its target when it is off by at least this share of paper equity (sim/book.py skips the
 * trade when the gap is strictly smaller).
 */
export const RESIZE_BAND = 0.01;

/**
 * Mirror of the engine's `TARGET_RESIZE_BAND = Decimal("0.20")` (sim/rules.py): for a rule set in
 * TARGET_BAND_RULES a held position is only traded back when it is off by at least this share of
 * its OWN target value (weight × equity), not of the whole account. In a 20-name book 1% of
 * equity is a fifth of one holding; in a 50-name book it is half of one, which is why the engine
 * grew the second basis.
 */
export const TARGET_RESIZE_BAND = 0.2;

/**
 * Engine rule sets with `resize_basis="target"` (sim/rules.py PRESETS). Their band is
 * TARGET_RESIZE_BAND of each holding target instead of RESIZE_BAND of equity. A hand mirror,
 * guarded by engine/tests/test_sean_mirrors.py; append when such a preset is added.
 */
export const TARGET_BAND_RULES: readonly string[] = [
  'monthly-hold-frac-gotrade-tband',
  'monthly-hold-frac-gotrade-tband-cash',
  'weekly-hold-frac-gotrade-tband-cash',
];

/** What a resize gap is measured against: the whole account, or the holding's own target. */
export type ResizeBasis = 'equity' | 'target';

/** The engine `resize_basis` of a rule set: 'target' for TARGET_BAND_RULES, else 'equity'. */
export function resizeBasisOf(rulesId: string | null | undefined): ResizeBasis {
  return typeof rulesId === 'string' && TARGET_BAND_RULES.includes(rulesId) ? 'target' : 'equity';
}

/**
 * What one book order means against what is held now, in dollars at tonight's marks and equity.
 * `buy`: not held, the whole target is bought. `add` / `trim`: held, the gap to the target.
 * `none`: held and inside the band (RESIZE_BAND of equity, or TARGET_RESIZE_BAND of the target on
 * the target basis), so the engine leaves it alone. `usd` is always >= 0 (0 for `none`).
 */
export type SizeChange = { action: 'buy' | 'add' | 'trim' | 'none'; usd: number };

/**
 * The order's dollar change: target `weight × equity` against `heldUsd`, the dollar value held now
 * (shares × current mark), or null when the symbol is not held. Approximate on purpose: the engine
 * sizes at the open's equity and the target's last close, the page at tonight's equity and marks.
 * `basis` is the rule set's (resizeBasisOf); the band it picks matches sim/book.py's.
 */
export function sizeChange(
  weight: number, equity: number, heldUsd: number | null, basis: ResizeBasis = 'equity',
): SizeChange {
  const target = weight * equity;
  if (heldUsd === null) return { action: 'buy', usd: Math.max(0, target) };
  const gap = target - heldUsd;
  const band = basis === 'target' ? TARGET_RESIZE_BAND * target : RESIZE_BAND * equity;
  if (Math.abs(gap) < band) return { action: 'none', usd: 0 };
  return gap > 0 ? { action: 'add', usd: gap } : { action: 'trim', usd: -gap };
}

/** Dollar value held now per symbol (the sum, should a symbol ever appear twice). */
export function heldUsd(holdings: readonly { symbol: string; value: number }[]): Map<string, number> {
  const out = new Map<string, number>();
  for (const h of holdings) out.set(h.symbol, (out.get(h.symbol) ?? 0) + h.value);
  return out;
}

/** `sizeChange` for one order row; null when the weight or the paper equity is not known. */
export function orderSizeChange(
  weight: number | null, equity: number | null, symbol: string, held: ReadonlyMap<string, number>,
  basis: ResizeBasis = 'equity',
): SizeChange | null {
  if (weight === null || equity === null) return null;
  return sizeChange(weight, equity, held.get(symbol) ?? null, basis);
}
```
**Change 8c:** `sizeTip` (:119-125) names the right band. The equity text is unchanged, so the existing `toContain('1%')` assertion still holds.
**Code:**
```ts
/** The cell's tooltip, in plain words. */
export function sizeTip(c: SizeChange, basis: ResizeBasis = 'equity'): string {
  if (c.action === 'buy') return 'Not held yet: the whole amount is bought at the open';
  if (c.action === 'add') return 'Held, but below its target: about this much more is bought at the open';
  if (c.action === 'trim') return 'Held, but above its target: about this much is sold at the open';
  if (basis === 'target') {
    return `Off its target by less than ${Math.round(TARGET_RESIZE_BAND * 100)}% of that target, too little to trade`;
  }
  return 'Off its target by less than 1% of paper equity, too little to trade';
}
```
**Impact:** every existing caller passes no basis and keeps today's behaviour exactly. Because
`TARGET_RESIZE_BAND × target` is computed as `0.2 × (weight × equity)`, a target of 100 gives a
band of exactly 20.0 in IEEE doubles (checked: `0.2*100 == 20.0`), so the "exactly at the band"
test in step 10 is not float-fragile.

### Step 9: `web/lib/sean/reminders.ts`: the resizing mirror and the basis-aware band
**File:** `web/lib/sean/reminders.ts`
**Change 9a:** the header rule (:13-15) replaces the add/trim bullet.
**Code:**
```ts
 *  - add / trim: only when the method's rules resize (engine `resize=True`), measured at the
 *    pick's decision price like the engine, and only when the gap is at least MIN_TRADE_USD and at
 *    least the engine's band: RESIZE_BAND of the plan, or, for a rule set on the target basis
 *    (cadence.ts TARGET_BAND_RULES), TARGET_RESIZE_BAND of that pick's own share of the plan
 *    (Gotrade's minimum fee makes smaller trades waste money).
```
**Change 9b:** the import (:33).
**Code:**
```ts
import { RESIZE_BAND, TARGET_RESIZE_BAND, type ResizeBasis } from '../cadence';
```
**Change 9c:** `RESIZING_RULES` (:64-76). The comment inside the array must contain **no single
quote**, because `test_sean_mirrors._string_array` collects every `'...'` in the block.
**Code:**
```ts
export const RESIZING_RULES: readonly string[] = [
  'monthly-hold',
  'monthly-hold-tbill',
  'monthly-hold-frac',
  'weekly-hold',
  'monthly-rank-weekly-resize',
  'monthly-rank-weekly-resize-tbill',
  'monthly-rank-weekly-resize-frac',
  // Gotrade real-fee twins of the two fractional presets (Sean phase 7); they resize the same way.
  'monthly-hold-frac-gotrade',
  'monthly-rank-weekly-resize-frac-gotrade',
  // The fixed-tape presets (measure-then-learn): they resize against each holding target,
  // so their band is cadence.ts TARGET_RESIZE_BAND (see TARGET_BAND_RULES).
  'monthly-hold-frac-gotrade-tband',
  'monthly-hold-frac-gotrade-tband-cash',
  'weekly-hold-frac-gotrade-tband-cash',
];
```
**Change 9d:** `ReminderInput` (:130-137) gains a required `resizeBasis` right after `resizes`.
**Code (the two fields as they read after the change):**
```ts
  /** resizes(rulesId) of the followed method. */
  resizes: boolean;
  /** resizeBasisOf(rulesId) of the followed method: which band an add or a trim must clear. */
  resizeBasis: ResizeBasis;
```
**Change 9e:** the band in `buildReminders` (:324-326).
**Code (replaces the three lines `if (!input.resizes ...` through the `Math.max` line):**
```ts
      if (!input.resizes || planSize === null) continue;
      const gap = t.weight * planSize - shares * t.last;
      const band = input.resizeBasis === 'target'
        ? TARGET_RESIZE_BAND * (t.weight * planSize)
        : RESIZE_BAND * planSize;
      if (Math.abs(gap) < Math.max(MIN_TRADE_USD, band)) continue;
```
**Impact:** `ReminderInput` gains a required field. `planData.ts` (step 11) and the test helper
(step 10) are the only constructors (`grep -rn buildReminders web/lib web/app`). `tsc --noEmit`
catches a missed one.

### Step 10: Web tests
**File:** `web/lib/cadence.test.ts`
**Change:** import the new names and add tests. Existing tests stay as they are.
**Code (import block, lines 2-5):**
```ts
import {
  cadenceOf, heldUsd, orderSizeChange, picksMonthlySizesWeekly, RESIZE_BAND, resizeBasisOf, sellsWhen,
  sizeChange, sizeLabel, sizeTip, SPLIT_CADENCE_RULES, TARGET_BAND_RULES, TARGET_RESIZE_BAND,
} from './cadence';
```
**Code (new describe block, appended at the end of the file):**
```ts
describe('the target-basis band', () => {
  it('mirrors the engine: a fifth of the holding target, for the fixed-tape rule sets only', () => {
    expect(TARGET_RESIZE_BAND).toBe(0.2);
    expect([...TARGET_BAND_RULES]).toEqual([
      'monthly-hold-frac-gotrade-tband',
      'monthly-hold-frac-gotrade-tband-cash',
      'weekly-hold-frac-gotrade-tband-cash',
    ]);
    for (const id of TARGET_BAND_RULES) expect(resizeBasisOf(id)).toBe('target');
    for (const id of ['monthly-hold-frac-gotrade', 'weekly-hold', 'design-v0', '']) {
      expect(resizeBasisOf(id)).toBe('equity');
    }
    expect(resizeBasisOf(null)).toBe('equity');
    expect(resizeBasisOf(undefined)).toBe('equity');
  });
  it('measures the gap against the target, trading at exactly the band and not under it', () => {
    // target 0.1 × 1000 = 100, so the band is 20 (the equity band would be 10)
    expect(sizeChange(0.1, 1000, 80, 'target')).toEqual({ action: 'add', usd: 20 });
    expect(sizeChange(0.1, 1000, 81, 'target')).toEqual({ action: 'none', usd: 0 });
    expect(sizeChange(0.1, 1000, 119, 'target')).toEqual({ action: 'none', usd: 0 });
    expect(sizeChange(0.1, 1000, 120, 'target')).toEqual({ action: 'trim', usd: 20 });
  });
  it('leaves alone a gap the equity band would trade', () => {
    expect(sizeChange(0.1, 1000, 85)).toEqual({ action: 'add', usd: 15 });
    expect(sizeChange(0.1, 1000, 85, 'target')).toEqual({ action: 'none', usd: 0 });
  });
  it('still buys a symbol that is not held, whatever the basis', () => {
    expect(sizeChange(0.005, 500, null, 'target')).toEqual({ action: 'buy', usd: 2.5 });
    expect(orderSizeChange(0.1, 1000, 'AAPL', heldUsd([{ symbol: 'AAPL', value: 85 }]), 'target'))
      .toEqual({ action: 'none', usd: 0 });
  });
  it('says which band in the tooltip', () => {
    expect(sizeTip({ action: 'none', usd: 0 }, 'target')).toContain('20%');
    expect(sizeTip({ action: 'none', usd: 0 }, 'target')).not.toContain('equity');
    expect(sizeTip({ action: 'none', usd: 0 }, 'equity')).toContain('1%');
  });
  it('knows the cadence of the fixed-tape rule sets', () => {
    expect(cadenceOf('monthly-hold-frac-gotrade-tband')).toBe('monthly');
    expect(cadenceOf('monthly-hold-frac-gotrade-tband-cash')).toBe('monthly');
    expect(cadenceOf('weekly-hold-frac-gotrade-tband-cash')).toBe('weekly');
    for (const id of TARGET_BAND_RULES) expect(picksMonthlySizesWeekly(id)).toBe(false);
  });
});
```

**File:** `web/lib/sean/reminders.test.ts`
**Change 10a:** the `input()` helper (:31-36) sets the basis explicitly.
**Code:**
```ts
function input(over: Partial<ReminderInput> = {}): ReminderInput {
  return {
    sessionDate: OCT, targets: RAW, resizes: true, resizeBasis: 'equity', held: new Map(), outside: new Map(),
    closes: new Map(), budgetUsd: null, cashUsd: null, orders: [], marks: [], ...over,
  };
}
```
**Change 10b:** the `resizes mirrors the engine presets` test (:449-457).
**Code:**
```ts
  it('resizes mirrors the engine presets', () => {
    expect(resizes('monthly-hold-frac')).toBe(true);
    expect(resizes('monthly-rank-weekly-resize-frac')).toBe(true);
    expect(resizes('monthly-hold-frac-gotrade')).toBe(true);
    expect(resizes('monthly-rank-weekly-resize-frac-gotrade')).toBe(true);
    expect(resizes('monthly-hold-frac-gotrade-tband')).toBe(true);
    expect(resizes('monthly-hold-frac-gotrade-tband-cash')).toBe(true);
    expect(resizes('weekly-hold-frac-gotrade-tband-cash')).toBe(true);
    expect(resizes('daily-switch')).toBe(false);
    expect(resizes('swing-t20')).toBe(false);
    expect(resizes(null)).toBe(false);
  });
```
**Change 10c:** a new describe block inserted right after the `describe('buildReminders: resizing', ...)` block (it ends just before `describe('buildReminders: done', ...)`, around :216).
**Code:**
```ts
describe('buildReminders: the target-basis band', () => {
  // Two picks of half the plan each: a $2,000 plan puts $1,000 in each. The equity band is
  // max($25, 1% of $2,000) = $25; the target band is max($25, 20% of $1,000) = $200.
  const HALVES: Target[] = [
    { symbol: 'AAA', weight: 0.5, last: 100 },
    { symbol: 'BBB', weight: 0.5, last: 50 },
  ];
  const holding = (aaaUsd: number, bbbUsd: number): Map<string, number> =>
    new Map([['AAA', aaaUsd / 100], ['BBB', bbbUsd / 50]]);

  it('on the equity basis a $100 gap is an add', () => {
    const r = buildReminders(input({ targets: HALVES, held: holding(900, 1000), budgetUsd: 2000 }));
    expect(r.open.map(x => `${x.action}:${x.symbol}`)).toEqual(['add:AAA']);
    expect(r.open[0].usd).toBeCloseTo(100, 6);
  });

  it('on the target basis the same gap is left alone, and a gap past a fifth of the target is not', () => {
    const r = buildReminders(input({
      targets: HALVES, held: holding(900, 1250), budgetUsd: 2000, resizeBasis: 'target',
    }));
    expect(r.open.map(x => `${x.action}:${x.symbol}`)).toEqual(['trim:BBB']);
    expect(r.open[0].usd).toBeCloseTo(250, 6);
  });

  it('the $25 floor still binds when a fifth of the target is smaller', () => {
    // 20 picks on an $838.16 plan: a fifth of a $41.91 share is $8.38, so $25 decides
    const held = followed();
    held.set('MU', 28 / 1045.56); // $13.91 below its share
    const r = buildReminders(input({ held, budgetUsd: 838.16, resizeBasis: 'target' }));
    expect(r.reminders).toHaveLength(0);
  });
});
```
**Impact:** test-only.

### Step 11: `web/lib/sean/planData.ts`: pass the basis
**File:** `web/lib/sean/planData.ts`. The import block (:11-14) and the `buildReminders({...})` call (:188-199).
**Change:** add the import and the field.
**Code (new import line, placed directly after `import { cache } from 'react';` and before `import { sql } from '@/lib/db';`):**
```ts
import { resizeBasisOf } from '@/lib/cadence';
```
**Code (the call, as it reads after the change):**
```ts
  const plan = buildReminders({
    sessionDate: decision?.sessionDate ?? l.since,
    targets: decision?.targets ?? [],
    resizes: resizes(l.rulesId),
    resizeBasis: resizeBasisOf(l.rulesId),
    held,
    outside,
    closes,
    budgetUsd: l.budgetUsd,
    cashUsd: cash,
    orders: inPlan.map(o => ({ symbol: o.symbol, side: o.side, executedAt: o.executedAt, price: o.price })),
    marks: marksDone,
  });
```
**Impact:** server-only file, no unit tests (its own docstring). Today every roster rule id
resolves to `'equity'`, so the page renders identically.

## Verification

**Setup (fresh worktree):**
```bash
cd /home/miftah/.worktrees/seer/measure-then-learn
python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
(cd web && npm ci)
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
```
**Build:** `engine/.venv/bin/ruff check engine && (cd web && npx tsc --noEmit)`
**Tests:**
```bash
engine/.venv/bin/pytest engine/tests/test_sim_rules.py engine/tests/test_sim_rules_fixed_tape.py \
  engine/tests/test_sean_mirrors.py engine/tests/test_lab_costs.py engine/tests/test_cost_model_pins.py \
  engine/tests/test_paper_kickoff.py engine/tests/test_registry.py engine/tests/test_paper_roster.py -n0
engine/.venv/bin/pytest engine/tests            # full suite, DB tests must not skip
(cd web && npm test)
```
**Manual check:** `git diff origin/main -- engine/src/seer_engine/paper/roster.py engine/tests/test_paper_roster.py` shows nothing from this phase (SEED_ROWS and PINS untouched). The web change is lib-only: no page markup changes, so no screenshot is needed.
**Exit criteria:**
- `PRESETS` has 19 entries, the last three being the fixed-tape presets in order.
- The full engine suite is green with Postgres. `test_every_recorded_configuration_still_digests_to_its_recorded_digest` and `test_paper_roster` PINS are unchanged and pass.
- `test_sean_mirrors` guards six names, including `TARGET_RESIZE_BAND` and `TARGET_BAND_RULES`.
- Web `tsc --noEmit` and `npm test` are green.

## Handoffs

- **Phase 5 / Phase 7 (lab methods):** import the presets from `seer_engine.sim.rules` (they are not re-exported from `seer_engine.sim`). Phase 7's ranker uses `MONTHLY_HOLD_FRAC_GOTRADE_TBAND`, which has no owner input and is promotable. Phase 5's twins may use all three. `lab.real_costs.real_cost_problem` accepts all three (book + gotrade).
- **Phase 2 (paper refusal):** the cash presets are now in `PRESETS`, so `roster.rules_for` resolves them. Phase 2's refusal sits in `promote._check_rules` and the paper night; Step 7's `test_promote_takes_the_band_preset_and_refuses_the_cash_presets` proves it fires for these real preset ids (reconciled: the test lives here).
- **Not done, deliberately (no phase owns it; future card):** `web/app/(app)/positions/page.tsx:148` calls `orderSizeChange` only for split-cadence rules (`picksMonthlySizesWeekly`), and none of the fixed-tape presets is split-cadence, so the size cell never shows them today. If a split-cadence target-basis preset is ever added, that call site should pass `resizeBasisOf(rulesId)` to `orderSizeChange` and to `sizeTip`, and the SizeCell doc comment at :606-609 should name the basis. It is left alone here because touching page markup is out of scope and would require the `run-the-web-app` visual check.
- **Possible cleanup (no phase):** the weekly real-fee rule set `weekly-hold-frac-gotrade` is redefined ad hoc in M0063, M0064, M0076 and M0085. Those are closed method files and must not be edited. A future preset would only help new methods.

## Rollback

Revert this phase's commit. Nothing recorded depends on the three presets until phase 5 or 7
runs a method on them. No roster row, pinned digest or lab row refers to them. After a lab method
has been **run** on them, the presets can no longer be removed: that method file imports them, and
its recorded config digest is frozen.

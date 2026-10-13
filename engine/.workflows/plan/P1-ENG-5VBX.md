> Adopted from `docs/plans/FOLD_VERDICT_AND_FALL_LABEL_PLAN.md` phase 5. Source: `.workflows/plan/fold-verdict-and-fall-label/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: Pre-register, run and record the fall-labelled method

**Plan set:** `FOLD_VERDICT_AND_FALL_LABEL_PLAN.md`
**Analysis:** `docs/analyzer/20261013-082101-K09L_code_analyzer.md`
**Satisfies:** R2 — "Learn the fall, not the pick": a model pointed at *exposure* instead of
*selection*, pre-registered as a new method id, run on the dev window and written up.
**Depends on:** Phase 1 (schema v7 + `method_folds`), Phase 2 (the fall label and the sizing head),
Phase 3 (the correcting insight — so this phase's own insight is appended *after* it and the two
read in the right order on `/sera`).
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab/methods/`, `lab/`, `docs/backtests/`

> **This phase mutates an append-only record and cannot be rolled back.** `trials`, `methods` and
> `insights` are append-only by trigger and the method id is spent the moment `lab run` returns 0.
> Every safeguard is in front of the run, not behind it: the dependency check, the exposure
> measurement, the test suite, the pre-registration commit and the fixed variant list. Read this
> whole file before running a single command.

---

## Goal

The lab gets one new pre-registered method whose model forecasts the **fall** over the coming
quarter and uses that forecast to decide **how much of the book to hold**, rather than which names
to hold. It is run once on the dev window beside two controls — the lab's one existing risk
control (the SPY 200-day switch) and no risk control at all — so that *model minus control* answers
the handover's actual question: can a learned downside forecast improve on the gate that "has never
been improved on". The result is recorded, staged, journalled in the owner's plain language and
written up against the hypothesis that was frozen before any number was seen.

## Interface Contract

**Creates:**
- `engine/src/seer_engine/lab/methods/m0132_fall_sized_book.py` — the method file. `0132` is the id
  `lab next-id` prints at run time; see **Step 2** for what to do if it has moved.
- `METHOD` with id `M0132`, family `model-sized-exposure`, five candidates:
  `M0132-FALL20`, `M0132-FALL20-REG`, `M0132-FALL20-GATE`, `M0132-GATE20`, `M0132-ON20`.
- Two allocator objects, both new and both only in this file:
  `FALL_BOOK` (`id = "M0132"`) and `SIZED_DV` (`id = "M0132-DV"`).
- Three params dataclasses in this file: `FallBookParams`, `FallBookPrepared`, `ControlParams`
  (+ `ControlPrepared`).
- `docs/backtests/2026-10-13-learn-the-fall.md` — the write-up.
- One `insights` row (`lab insight --kind observation`).
- Database rows: one `methods` row, five `trials` + their `trial_moments` / `trial_funding` /
  `trial_provenance`, one `method_folds` row (phase 1's), one `insights` row, `ideas_seen` rows.

**Deletes:** nothing.
**Renames:** nothing.
**Signature changes:** none. **No engine source outside `lab/methods/` is edited by this phase.**

**Requires (from earlier phases) — read this before writing a line of the method file:**

1. **Phase 1:** `store.SCHEMA_VERSION == "7"` and a `method_folds` table in `lab/lab.sqlite`.
   Measured on the worktree *today*, before phase 1 landed: `schema_version` is `6` and
   `.tables` shows no `method_folds`. `store._migrate` refuses an unknown version, so this is a
   hard stop, not something to work around.
2. **Phase 2 — the names are SETTLED, not assumed.** The reconciler resolved this against phase 2's
   landed Interface Contract. `seer_engine.lab.tree_rank` exports:

   | Name | What it is |
   |---|---|
   | `FALL_SIZE` | `FallSizeAllocator("price")`, `id == "FALL"` — the **only** fall allocator |
   | `FallSizeParams` | the frozen params dataclass, with `as_dict() -> dict[str, str]` |
   | `QUARTER` | 63 |
   | `FALL_FEATURE_LOOKBACK` | 401 |

   The book-size field is **`slots`**, not `top_n`. Everything else this plan passes by keyword —
   `horizon`, `train_start`, `min_train_months`, `max_iter`, `max_leaf_nodes`, `min_samples_leaf`,
   `l2` — carries the same name and meaning as in `TreeRankParams`. **There is no
   `FALL_SIZE_FUND`** (D14): the EDGAR panel starts in 2009, no method may pre-register on it
   (D8), and exporting an allocator nothing can use would claim the id `FALLF` for ever. Importing
   it is an `ImportError`, by design.

3. **Phase 2 — the label is a LEVEL, not a per-date rank (D13). This changes the pre-registration,
   not just the import block.** The superseded draft of phase 2 applied `rank01` to the fall
   measure. It no longer does, for the reason this plan's own *Requires (3)* raised and the
   reconciler upheld: `tree_rank.rank_columns` already rank-normalises every **feature** per date,
   so a per-date rank **label** on top of that leaves the prediction distribution near-stationary
   across dates by construction — in October 2008 the per-date ranks are *still uniform*, so the
   label cannot encode "all of them" even in principle, and the method would have been a selection
   test wearing a sizing head. What phase 2 now ships, and what this method's `hypothesis` must
   therefore describe:

   - **the label is the raw forward fall** — the drawdown fraction (or the realised downside
     volatility) over the next quarter, in its own units, NaN where unmeasurable;
   - **the feature matrix is ten columns, not seven**: the ranker's seven rank-normalised features
     plus three **un-normalised, market-level** columns — SPY's distance below its trailing
     252-session high, SPY's realised volatility over the last 60 sessions, and the cross-sectional
     dispersion of the date's own momentum. Each is a per-date scalar broadcast down the rows, so
     it cannot change which names the model prefers, only how far the whole date's forecast moves;
   - **the head reads a market-level quantity**: the date's cross-sectional *mean* predicted fall is
     located in the model's own training distribution of date-level means, and the book holds
     `slots - floor(danger * slots)` whole slots, where `danger` is the share of training dates that
     looked no more dangerous. Calmer than every training date → a full book; worse than all of them
     → cash; at the median → half. **There is no exposure ladder for this phase to choose and no
     threshold for it to pre-register** — the ladder is the model's own empirical CDF, so nothing in
     it was read off the dev window;
   - **the reach is unchanged at 401 sessions** (`FALL_FEATURE_LOOKBACK`), under the smoke fixture's
     473-bar cap.

   **Phase 2 also now owns the exposure measurement.** Its exit criterion **M5b** runs the probe on
   the real research store across the January decision dates 2000-2015 and fails *phase 2* if the
   exposure is flat or does not fall in 2008 — so this phase does not start unless that already
   passed. Step 3 below is kept as a **pre-commit re-check**, and the redundancy is deliberate: the
   method id is irreversible and the two checks run on different days.

4. **Phase 3:** the correcting insight row is committed, so this phase's insight is strictly newer.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/tree_rank.py` (Phase 2) — read, never edited.
- `engine/src/seer_engine/lab/store.py`, `hardgate.py`, `runner.py`, `commands/lab.py` (Phase 1).
- `engine/src/seer_engine/lab/turnover.py`, `docs/backtests/2026-10-13-chart-model-turnover.md` (Phase 4).
- `engine/src/seer_engine/lab/methods/m0130_tree_ranker.py` — imported (`model_ready`), never edited.
  It is frozen against its recorded sha.
- The test window: no `lab test`, no `lab promote`, `engine/.research-test` is never named.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0132_fall_sized_book.py` | create | the whole method file (Step 4) |
| `lab/lab.sqlite` | append | method row, 5 trials + side rows, 1 `method_folds` row, 1 insight |
| `web/data/lab.json` | regenerate | `lab stage`'s export of the above |
| `docs/backtests/2026-10-13-learn-the-fall.md` | create | the write-up (Step 9) |

No line of existing code is touched. There is no "line reference where the change lands" for a
file this phase only creates; every edit location below is a whole new file.

---

## Design: what the five variants are, and what each paired difference isolates

Fixed now, before any result, and never revised afterwards (**D10**).

| Variant | Allocator | What it is |
|---|---|---|
| `M0132-FALL20` | `FALL_BOOK` | The fall model sizes a 20-name book. Base tree. |
| `M0132-FALL20-REG` | `FALL_BOOK` | The same, with the one fixed regularised tree. |
| `M0132-FALL20-GATE` | `FALL_BOOK` | The same base model, *also* behind the SPY 200-day switch. |
| `M0132-GATE20` | `SIZED_DV` | **CONTROL.** The same 20 names, sized only by the SPY 200-day switch. |
| `M0132-ON20` | `SIZED_DV` | **CONTROL.** The same 20 names, always fully invested. No risk control. |

Every variant holds the **same names**: the 20 screen-eligible index members with the largest
20-day dollar volume (`tree_rank.SCREEN`, the tree's own screen). Only *how much of the book is
held* differs. That is what makes the differences below clean.

**Why dollar volume picks the names (D11 and D12 together).** Dollar volume forecasts nothing — it
is the same yardstick M0130 used as its control, and it is deliberately **not** momentum. The hard
gate's behavioural kin test (`hardgate.KIN_CORRELATION = 0.85`, D14) compares *every* dev variant
of a method against the four test-failed books' tested variants, and one match bars the whole
method from promotion forever. Three of the four test-failed books are momentum books
(`M0002` `stock-momentum-risk-managed`, `M0022` `stock-residual-momentum`, plus `M0021`/`M0029` in
`stock-multi-factor-blend`, whose blend has a momentum leg). The kin test correlates curves *after
removing each series' fit on SPY's*, so a residual that is momentum-tilt-shaped is what trips it. A
dollar-volume-picked large-cap book has a size/liquidity-shaped residual, not a momentum-shaped
one, and no variant of this method ever ranks on momentum, in any era, at any exposure. **Step 3b
measures this rather than asserting it**, read-only, before the pre-registration commit.

**Family.** `model-sized-exposure` — a new family. The three families that already hold a
`test-failed` method are `stock-residual-momentum`, `stock-momentum-risk-managed` and
`stock-multi-factor-blend`; filing under any of those would bar this method by family kin (D4)
before it ran. `stock-ml-ranker` is clean but is about *ranking*, which is exactly what the
handover says this method is not.

**The paired differences, named now:**

| Difference | What it isolates |
|---|---|
| `GATE20` − `ON20` | What the lab's one existing risk control is worth on this exact book. The yardstick, re-priced on the same names and the same calendar. |
| `FALL20` − `ON20` | Everything the learned fall forecast adds over no risk control at all. |
| **`FALL20` − `GATE20`** | **The handover's actual question**: does a learned downside forecast improve on the SPY 200-day gate? |
| `FALL20-GATE` − `GATE20` | Whether the model sees anything the gate has not already taken out. |
| `FALL20-REG` − `FALL20` | Whether any of the above is a model-capacity artefact rather than a signal. |

**The shared calendar.** Every variant, both controls included, holds SPY at full weight until the
first model exists — the same `model_ready` calendar rule M0130 used, imported from M0130's file
rather than re-written, so the pre-model era is byte-identical between the two methods. With a
63-session label and 35 required labelled month-ends the first refit with enough history is
**1999-12-31**, not M0130's 1998-12-31 (a quarter-long label is read three months later, so only 33
month-ends from 1996-01-31 have labels by 1998-12-31). The book is therefore SPY through 1999 in
all five variants. That is pre-registered and stated in the hypothesis; it is identical across
variants, so it cancels out of every difference above.

**Why not six variants.** Every setting tried counts (D10). Five answers the question; a sixth
would only add a hyperparameter. No fundamentals variant (**D8**) — every variant ranks on price
and dividend features only, so `market_fields` never names `fundamentals`, the coverage floor is
never engaged and `--allow-coverage` is never passed; and phase 2 exports no fundamentals allocator
at all (**D14**), so there is nothing to pre-register one on.

**And specifically not a per-date-rank-label control.** The reconciliation considered spending the
sixth slot on the design D13 removed — a `label="rank"` arm that would *demonstrate* the flat
exposure rather than predict it. It is **not** taken: carrying the rank path at all would mean phase
2 shipping a label mode it is supposed to have deleted, and this method's own rule is that every
setting tried counts and a sixth would only add a hyperparameter. The prediction stays where a
prediction belongs — in `expected_failure`, above — and the design that would have produced it is
gone from the tree rather than parked in it (**D2f** in phase 2).

**Why `MONTHLY_HOLD_FRAC_GOTRADE_TBAND` and not the `_CASH` preset.** The cash-crediting preset
raises the owner input `cash-yield`, which paper refuses, and M0130 ran on the plain preset. Idle
cash earning nothing is the conservative reading and the one the owner can actually trade. It
biases every exposure-reducing variant downward — but `GATE20` sits in cash too, so the
`FALL20` − `GATE20` difference, which is the question, absorbs almost all of that bias. Both facts
are written into the hypothesis and the expected failure.

---

## Implementation Steps

### Step 1: Verify the three dependencies have landed. If one has not, WAIT.

**File:** none — read-only checks.
**Change:** refuse to start until phases 1, 2 and 3 are in the tree.

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label

# Phase 1 — schema v7 and the method_folds table.
grep -n '^SCHEMA_VERSION' engine/src/seer_engine/lab/store.py
sqlite3 'file:lab/lab.sqlite?mode=ro' "SELECT value FROM meta WHERE key='schema_version';"
sqlite3 'file:lab/lab.sqlite?mode=ro' ".tables" | tr ' ' '\n' | grep -x method_folds

# Phase 2 — the settled names, the LEVEL label and the market columns are all in place.
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
import seer_engine.lab.tree_rank as tr
print("FALL_SIZE.id        ", tr.FALL_SIZE.id)                 # FALL
print("QUARTER             ", tr.QUARTER)                      # 63
print("FALL_FEATURE_LOOKBACK", tr.FALL_FEATURE_LOOKBACK)       # 401
print("MARKET_FEATURES     ", tr.MARKET_FEATURES)              # 3 un-normalised level columns
print("slots field         ", "slots" in tr.FallSizeParams().as_dict())   # True, not top_n
print("no fund object      ", not hasattr(tr, "FALL_SIZE_FUND"))          # True (D14)
PY

# Phase 3 — the correcting insight is committed.
sqlite3 'file:lab/lab.sqlite?mode=ro' "SELECT n, kind, title FROM insights ORDER BY n DESC LIMIT 3;"
git log --oneline -12
```

**Expected:** `SCHEMA_VERSION = "7"`, `schema_version` reads `7`, `method_folds` is in `.tables`,
every line of the phase-2 block prints as commented (`FALL`, `63`, `401`, the three market
features, `True`, `True`), and the newest insight is phase 3's correction to insight 217.

**Also required before starting: phase 2's M5b passed.** Phase 2's exit criterion 9 is the
real-store exposure measurement (exposure on the January decision dates 2000-2015 takes at least
three distinct values and 2008 is below 2005). Ask the coordinator for phase 2's report, or read it
from phase 2's commit body. **If phase 2 reported M5b as failing, this phase does not run at all** —
the method id is not spent on a book that cannot change its exposure.

**Measured today, before any phase landed:** `SCHEMA_VERSION = "6"`, `schema_version` = `6`, no
`method_folds` table, `tree_rank` has no fall names. **So this phase cannot start yet.**

**Impact:** `store._migrate` refuses an unknown version. A `lab run` against a v6 database with v7
code, or against a v7 database with v6 code, is a hard stop. If any check fails, stop and wait for
the phase that owns it; do not "fix" it from here.

---

### Step 2: Take the method id from `lab next-id`, not from this plan.

**File:** none yet.
**Change:** read the id and bind the file name, the module number and `METHOD.id` to it.

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
sqlite3 'file:lab/lab.sqlite?mode=ro' "SELECT id,status,family,name FROM methods ORDER BY id DESC LIMIT 5;"
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab next-id
```

**Measured 2026-10-13 (read-only):** the highest row is `M0131` (`idea`, `stock-ml-ranker`, "A
slower target for the learned ranker…"), a **different question** from this one, so
`store.next_method_id` returns **`M0132`**.

**If the printed id is not `M0132`** — a peer session may have registered an idea in the meantime —
then everywhere this plan says `M0132` or `m0132`, substitute the printed id:

- the file name `engine/src/seer_engine/lab/methods/m<NNNN>_fall_sized_book.py`;
- `METHOD = Method(id="M<NNNN>", ...)`;
- the two allocator ids, `"M<NNNN>"` and `"M<NNNN>-DV"`;
- the five candidate ids, `M<NNNN>-FALL20` … `M<NNNN>-ON20`;
- the `_v()` helper's `f"M<NNNN>-{suffix}"` and `family="M<NNNN>"`;
- the module docstring's first line and the commit messages.

`method.discover()` raises `ValueError` when a module's number disagrees with its `METHOD.id`, and
`Candidate.family` must equal the method id, so a half-done rename fails loudly at import — which
is the point. Rename the file with `git mv` if it has already been added.

**Impact:** none yet; nothing is written.

---

### Step 2b: Confirm phase 2's names against the landed code. They are already settled.

**File:** the import block of the new method file.
**Change:** none, unless the landed code disagrees with the table below — in which case **stop and
report**, because a disagreement means phase 2 did not land what it was reconciled to.

The reconciler resolved the names against phase 2's Interface Contract. This plan uses them
directly; there is no longer anything to choose here:

| Name | What it is |
|---|---|
| `FallSizeParams` | the fall model's frozen params dataclass, `as_dict() -> dict[str, str]` |
| `FALL_SIZE` | `FallSizeAllocator("price")`, `id == "FALL"` — the only fall allocator |
| `QUARTER` | 63 |
| `FALL_FEATURE_LOOKBACK` | 401 |

`FallSizeParams` carries, among others, the fields this plan passes **by keyword only**:

`slots`, `size`, `measure`, `horizon`, `train_start`, `min_train_months`, `max_iter`,
`max_leaf_nodes`, `min_samples_leaf`, `l2`

**The book-size field is `slots`, not `top_n`.** The pre-registered meanings are fixed and must not
move: `horizon` is 63 sessions, `train_start` 1996-01-31, `min_train_months` 35, and the regularised
tree is 100 trees / 7 leaves / 1,000 per leaf / L2 10 — M0130's one fixed alternative re-used
verbatim, so the two methods' "regularised" arm means the same thing.

**There is no exposure ladder to pre-register here** (D13). The superseded draft of this step asked
for one to be invented in the method file if phase 2's head took step sizes. It does not: the head
locates the date's cross-sectional mean predicted fall in the model's own training distribution of
date-level means and holds `slots - floor(danger * slots)` whole slots. The ladder is the model's
own empirical CDF, so there is nothing for this phase to choose and nothing that could have been
read off the dev window. A whole slot is 5% of equity at 20 slots, five times
`sim.rules.TARGET_RESIZE_BAND` (20% of a name's **own** target) at every book size — phase 2's D7
measurement — so every step this head takes is one the measuring tape can hear. **Do not improvise
a head here under any circumstances**: an improvised head is a different question from the one
pre-registered, and the pre-registration would be a fiction.

**Impact:** the method file imports two names from `tree_rank` and nothing else from phase 2.

---

### Step 3: Re-measure that the sizing head actually moves. HARD STOP if it does not.

**File:** `/tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/exposure_probe.py` (throwaway).
**Change:** none to the repo. This spends no method id, writes no trial and opens no database.

**This is a re-check, not the first check.** Phase 2 owns this measurement as its exit criterion
**M5b** and fails itself if the head cannot move exposure (D13). It is repeated here, immediately
before the pre-registration commit, **because the method id is irreversible and the two checks run
on different days against possibly different code.** The redundancy is deliberate; do not skip it
because phase 2 already reported a pass.

It loads the real research store, builds phase 2's prepared value, and prints the **sum of target
weights** — the realised exposure — on the January decision date of every year from 2000 to 2015,
beside the always-full control.

**Code:**

```python
"""Does the fall model's head actually move exposure? Read-only, writes nothing.

Run BEFORE the pre-registration commit, as a re-check of phase 2's own M5b. If the printed
exposure is the same number on every line, the head carries no market-wide level and the book
is fully invested on every date -- which makes this method M0130's dollar-volume control with a
new id. Stop and report.

Only exposure counts are printed: no return, no drawdown, no profit factor. This is a design
sanity check on the DEV window, not a look at a result, and the test window is not touched.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from seer_engine import dates, research
from seer_engine.lab.tree_rank import FALL_SIZE, FallSizeParams  # phase 2's settled names

STORE = Path("/home/miftah/seer/engine/.research")
HORIZON = 63
TRAIN_START = date(1996, 1, 31)
MIN_TRAIN_MONTHS = 35


def main() -> None:
    data = research.load_store(STORE)
    market = data.market
    params = FallSizeParams(
        slots=20,                       # NOT top_n: phase 2's field is `slots`
        horizon=HORIZON,
        train_start=TRAIN_START,
        min_train_months=MIN_TRAIN_MONTHS,
    )
    control = FallSizeParams(
        slots=20,
        size=False,                     # the always-full control: must read 1.000 every line
        horizon=HORIZON,
        train_start=TRAIN_START,
        min_train_months=MIN_TRAIN_MONTHS,
    )
    prepared = FALL_SIZE.prepare_market(market)
    print(f"store {data.fingerprint[:12]}  prices {data.price_fingerprint[:12]}")
    print(f"{'date':<12}{'names':>7}{'exposure':>11}{'control':>10}")
    for year in range(2000, 2016):
        d = dates.prev_session(date(year, 2, 1))
        members = market.membership.members_on(d)
        got = FALL_SIZE.targets_prepared(prepared, members, d, frozenset(), params)
        ctl = FALL_SIZE.targets_prepared(prepared, members, d, frozenset(), control)
        w = float(sum(float(t.weight) for t in got))
        c = float(sum(float(t.weight) for t in ctl))
        print(f"{d.isoformat():<12}{len(got):>7}{w:>11.3f}{c:>10.3f}")


if __name__ == "__main__":
    main()
```

**Command:**

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python \
  "$SCRATCHPAD/exposure_probe.py" 2>&1 | tee "$SCRATCHPAD/exposure_probe.out"
```

Loading the store from the main checkout was measured at about **13 seconds**; the yearly refits
dominate, so budget a few minutes.

**Pass:** the exposure column takes at least three distinct values across the sixteen lines, and
2008 is visibly lower than 2005, with the `control` column flat at `1.000` on every line. **That is
the whole point of the method**, and it must agree with what phase 2 reported for M5b.

**Fail — and this is a HARD STOP:** every line reads the same exposure (typically `1.000`), or
2008 is not below 2005. The head is not carrying a market-wide level. That is phase 2's design
(D13: the raw level label and the three un-normalised market columns), so it is **phase 2's bug to
fix, never this phase's**. **Do not improvise a head in the method file** — an improvised head is a
different question from the one planned, and the pre-registration would be a fiction. Stop, report
to the coordinator with this output attached beside phase 2's own M5b output, and wait. The method
id is not spent on a fully-invested book.

**If the two outputs disagree** — phase 2 reported a pass and this run reads flat — say so
explicitly in the report: something landed between them, and that is a worse problem than either
result alone.

**Impact:** nothing is written. The only cost is a few minutes of compute, against a method id that
cannot be given back.

---

### Step 3b: Measure the behavioural-kin risk (D12) before committing, read-only.

**File:** none.
**Change:** none. One read of the lab's own kin routine.

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
from seer_engine.lab import hardgate, store
conn = store.connect_readonly()
print("KIN_CORRELATION =", hardgate.KIN_CORRELATION)
print("M0130 failed kin:", hardgate.failed_kin(conn, "M0130"))
PY
```

M0130's recorded `M0130-DV20` is the **same dollar-volume book** this method's controls use, so its
kin reading is the closest thing to a direct measurement of this method's kin risk.

`failed_kin` returns method ids only — no returns, no curves — so this is not a test-window look
and nothing is printed or reasoned about that is not already in the handover.

**Pass:** `failed_kin(conn, "M0130")` returns `()`. The dollar-volume book does not read as kin to
the four test-failed books, so neither will any exposure-reduced version of it (reducing exposure
moves a curve toward cash, away from a fully-invested momentum book, not toward it).

**If it returns ids:** the picking base is already kin and every variant of this method would be
unpromotable before it ran. Stop and report; do not switch the picking rule to something else
mid-plan, because the control's meaning is part of the pre-registration.

**Impact:** none.

---

### Step 4: Write the method file.

**File:** `engine/src/seer_engine/lab/methods/m0132_fall_sized_book.py` (new, whole file)
**Change:** the complete pre-registration. The `hypothesis` and `expected_failure` below are
written **now, before any result**, and the commit in Step 7 freezes them.

**Code:**

```python
"""M0132 -- Learn the fall, not the pick: a model that sizes the book, not its names.

Source: Moreira & Muir (2017), "Volatility-Managed Portfolios", Journal of Finance 72(4).
Handover 2026-10-13 ("measure the constraint"), section 2 item 2.

WHY THIS AND NOT ANOTHER RANKER. The lab's own record says the binding constraint is the fall, not
the pick: of 394 dev trials with a recorded return, 256 (65%) beat SPY total return but only 92
(23%) keep the worst fall at or under 20%. Out of sample it inverts -- all four spent test looks
failed on return. A two-thirds dev hit rate that vanishes out of sample is the signature of
selection, and more selection is the one thing this lab should stop buying. Against that, the lab
has exactly ONE risk control -- the SPY 200-day switch -- and it has never been improved on. So
this method points the same walk-forward, point-in-time machinery M0130 used at a different
question: not "which names will go up" but "how much of this book should be held".

THE LABEL is the forward FALL, AS A LEVEL: the worst peak-to-trough drop over the next quarter (63
NYSE sessions), in fractions, not the next month's return rank and not a rank of the fall either.
That distinction is the method. Every FEATURE the lab computes is already rank-normalised within
its date; a label ranked the same way would leave the model's forecasts near-identical on every
date by construction, and in October 2008 -- when every name is about to fall -- the per-date ranks
are still uniform, so the label could not say "all of them" even in principle. A level can.

THE FEATURE MATRIX therefore carries a level too, or the level label would buy nothing: the seven
rank-normalised features the lab already computes, plus three un-normalised market-level columns --
the market's distance below its trailing one-year high, its realised volatility over the last sixty
sessions, and the spread of the day's own momentum across the cross-section. Each is one number for
the whole date, repeated down the rows, so it cannot change which names the model prefers; it can
only move the whole date's forecast up or down. That is the level the head reads.

THE HEAD turns the forecast into EXPOSURE -- what share of the book is held, with the remainder in
cash -- rather than into a pick order, and it reads a MARKET-LEVEL quantity to do it. The date's
cross-sectional MEAN forecast fall is located in the model's own training distribution of
date-level means; the book keeps the share of its slots that the date is calmer than, in whole
slots, each at a fixed weight, never renormalised onto the survivors. A date calmer than every
training date is a full book; a date worse than all of them is entirely cash; the median date is
half. NO NUMBER IN THAT LADDER WAS CHOSEN: it is the model's own in-sample distribution, so nothing
in this head was read off the dev window, which is what pre-registration requires.

All of that lives in ``lab.tree_rank`` beside the return-rank path; nothing in that module that
M0130's six recorded configurations depend on is touched.

THE NAMES ARE NOT THE QUESTION, and are therefore held fixed. Every variant, model and control
alike, holds the twenty screen-eligible index members with the largest 20-day dollar volume
(``tree_rank.SCREEN``, the tree's own screen). Dollar volume forecasts nothing -- it is the
yardstick M0130 used as its control -- so the only thing that differs between variants is how much
of that same book is held, and every paired difference below is the sizing alone.

IT IS DELIBERATELY NOT A MOMENTUM BOOK. The hard gate's behavioural kin test
(``lab/hardgate.py`` D14, ``KIN_CORRELATION`` 0.85) reads EVERY dev variant of a method against the
four test-failed books' tested variants, and one match bars the whole method from promotion
forever. Three of those four are momentum books. A dollar-volume book's residual, once each
series' fit on SPY is removed, is size- and liquidity-shaped, not momentum-shaped; and no variant
here ranks on momentum in any era at any exposure.

BEFORE THE FIRST MODEL, HOLD SPY. ``model_ready`` is M0130's calendar rule, imported rather than
re-written so the pre-model era of the two methods is identical. With a 63-session label and 35
required labelled month-ends the first refit with enough history is 1999-12-31 (only 33 month-ends
from 1996-01-31 have their quarter-long label read by 1998-12-31), so the book is SPY through 1999
in all five variants. It is calendar-only and shared with the controls, which have no model, so
every variant switches on the same session and the pre-model era cancels out of every difference.

THE FIVE VARIANTS are the only settings this idea will ever try. None was chosen by looking at a
dev result and none will be revised after one; a change after a result is a new method.

    FALL20       the fall model sizes the twenty-name book, base tree
    FALL20-REG   the same, with the one fixed regularised tree (M0130's REG, verbatim)
    FALL20-GATE  the same base model, also behind the lab's standing SPY 200-day switch
    GATE20       CONTROL: the same twenty names, sized only by the SPY 200-day switch
    ON20         CONTROL: the same twenty names, always fully invested, no risk control

IDLE CASH EARNS NOTHING here (``MONTHLY_HOLD_FRAC_GOTRADE_TBAND``, M0130's rule set). The
cash-crediting preset raises an owner input paper refuses, and this is the version the owner can
actually trade. It biases every exposure-reducing variant downward -- but GATE20 sits in cash too,
so the FALL20-minus-GATE20 difference, which is the question, absorbs nearly all of that bias.

NO FUNDAMENTALS VARIANT. The EDGAR panel starts in 2009; a panel-gated variant would be all-cash
for thirteen of the dev window's twenty years and would measure the panel rather than the
hypothesis. Every variant ranks on price and dividend features only, so the coverage floor is never
engaged and this method never runs under ``--allow-coverage``.

Pure: no clock, randomness, files, network or printing. Reads only data dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0130_tree_ranker import model_ready
from seer_engine.lab.tree_rank import (
    FALL_FEATURE_LOOKBACK,
    FALL_SIZE,
    SCREEN,
    FallSizeParams,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorPrepared,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 13)
BENCH = "SPY"  # held before the first model, and the gate's instrument
GATE = N20  # the lab's standing SPY 200-day switch (F4-MOM12-N20-TREND's), read only for its trend

# The decision calendar, written once and shared by the model and both controls, so that
# `model_ready` fires on the same session for all five variants.
TRAIN_START = date(1996, 1, 31)
MIN_TRAIN_MONTHS = 35
HORIZON = 63  # one quarter: the window the forward fall is measured over
TOP_N = 20  # the book's size, identical in every variant

#: The base tree: Strategy B's pre-registered setting (lr 0.05, 300 iters, 15 leaves, 200/leaf,
#: L2 1), fixed 2026-10-03 for a different book and never searched. `slots` is phase 2's field
#: name for the book's size; `size=True` (the default) switches the exposure ladder on.
BASE = FallSizeParams(
    slots=TOP_N,
    horizon=HORIZON,
    train_start=TRAIN_START,
    min_train_months=MIN_TRAIN_MONTHS,
)
#: The one fixed alternative: fewer, shallower, fatter-leaved trees. M0130's REG, verbatim, so
#: "regularised" means the same thing in both methods.
REG = FallSizeParams(
    slots=TOP_N,
    horizon=HORIZON,
    train_start=TRAIN_START,
    min_train_months=MIN_TRAIN_MONTHS,
    max_iter=100,
    max_leaf_nodes=7,
    min_samples_leaf=1000,
    l2=10.0,
)


def _bench(history: Mapping[str, History], data_date: date) -> tuple[Target, ...]:
    """SPY at full weight, priced at d's close; nothing when SPY has no bar dated d."""
    h = history.get(BENCH)
    if h is None or h.index_of(data_date) is None:
        return ()
    t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
    return () if t is None else (t,)


# --------------------------------------------------------------------------- the model book


@dataclass(frozen=True, slots=True)
class FallBookParams:
    """The fall model's own params, and whether the SPY 200-day switch stands in front of it."""

    fall: FallSizeParams
    gate: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.fall, FallSizeParams):
            raise TypeError(f"fall must be FallSizeParams, got {type(self.fall).__name__}")
        if not isinstance(self.gate, bool):
            raise TypeError(f"gate must be a bool, got {type(self.gate).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = dict(self.fall.as_dict())
        out["gate"] = "SPY:200" if self.gate else "none"
        return out


@dataclass(frozen=True, slots=True, eq=False)
class FallBookPrepared:
    """The inner model's prepared value, and the bars the SPY fill and the gate read.

    ``history`` is None on the history-only path, which by the market-aware contract targets
    nothing (tests/test_lab_methods.py).
    """

    inner: Any
    history: Mapping[str, History] | None


class FallBook:
    """Phase 2's fall-sizing book, SPY before its first model, optionally behind the SPY switch."""

    def __init__(self, inner: Any, ident: str) -> None:
        self.inner = inner
        self.id = ident
        # What `lab run` gates on (runner.market_fields): exactly the inner model's fields.
        self.market_fields: tuple[str, ...] = tuple(inner.market_fields)

    def _check(self, params: object) -> FallBookParams:
        if not isinstance(params, FallBookParams):
            raise TypeError(f"params must be FallBookParams, got {type(params).__name__}")
        return params

    def lookback(self, params: Any) -> int:
        p = self._check(params)
        n = self.inner.lookback(p.fall)
        return max(n, factor_lookback(GATE)) if p.gate else n

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = self._check(params)
        return tuple(sorted({BENCH, *self.inner.symbols(p.fall)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        self._check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        self._check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """History-only path: no membership history, no calendar, no model, so no target."""
        self._check(params)
        return ()

    def prepare(self, history: Mapping[str, History]) -> FallBookPrepared:
        return FallBookPrepared(self.inner.prepare(history), None)

    def prepare_market(self, market: Any) -> FallBookPrepared:
        return FallBookPrepared(
            self.inner.prepare_market(market), MappingProxyType(dict(market.history))
        )

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if not isinstance(prepared, FallBookPrepared):
            raise TypeError(f"prepared must be FallBookPrepared, got {type(prepared).__name__}")
        if prepared.history is None:
            return ()
        if p.gate and not trend_on(prepared.history, data_date, GATE):
            return ()
        if not model_ready(data_date, p.fall.train_start, p.fall.min_train_months, p.fall.horizon):
            return _bench(prepared.history, data_date)
        return self.inner.targets_prepared(prepared.inner, members, data_date, held, p.fall)


FALL_BOOK = FallBook(FALL_SIZE, "M0132")


# --------------------------------------------------------------------------- the controls


@dataclass(frozen=True, slots=True)
class ControlParams:
    """The control's book size, whether the SPY switch sizes it, and the clock it shares.

    The clock defaults are the model's own (``BASE``), so `model_ready` fires on the same session
    for a control as for a model variant and the pre-model era cancels out of every difference.
    """

    top_n: int = TOP_N
    gate: bool = False
    train_start: date = BASE.train_start
    min_train_months: int = BASE.min_train_months
    horizon: int = BASE.horizon

    def __post_init__(self) -> None:
        for name in ("top_n", "min_train_months", "horizon"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
            if v < 1:
                raise ValueError(f"{name} must be >= 1, got {v}")
        if self.top_n > 100:
            raise ValueError(f"top_n must be <= 100, got {self.top_n}")
        if not isinstance(self.gate, bool):
            raise TypeError(f"gate must be a bool, got {type(self.gate).__name__}")
        if not isinstance(self.train_start, date):
            raise TypeError(f"train_start must be a date, got {type(self.train_start).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {
            "top_n": str(self.top_n),
            "gate": "SPY:200" if self.gate else "none",
            "train_start": self.train_start.isoformat(),
            "min_train_months": str(self.min_train_months),
            "horizon": str(self.horizon),
        }


@dataclass(frozen=True, slots=True, eq=False)
class ControlPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared


class SizedVolumeBook:
    """The model book's shape without the model: the most-traded eligible members, equal weight.

    ``gate=False`` is the no-risk-control floor: always fully invested once the model era starts.
    ``gate=True`` is the lab's one existing risk control -- the SPY 200-day switch -- sizing the
    same book, which is the yardstick the handover says has never been improved on.
    """

    id = "M0132-DV"

    def _check(self, params: object) -> ControlParams:
        if not isinstance(params, ControlParams):
            raise TypeError(f"params must be ControlParams, got {type(params).__name__}")
        return params

    def lookback(self, params: Any) -> int:
        p = self._check(params)
        n = FALL_FEATURE_LOOKBACK  # the model's window, so all five variants score the same sessions
        return max(n, factor_lookback(GATE)) if p.gate else n

    def symbols(self, params: Any) -> tuple[str, ...]:
        self._check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        self._check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        self._check(params)
        return True

    def _pick(self, rows: list[Any], p: ControlParams) -> tuple[Target, ...]:
        chosen = sorted(rows, key=lambda r: (-r.dollar_volume, r.symbol))[: p.top_n]
        w = equal_weight(p.top_n)
        out: list[Target] = []
        for row in chosen:
            t = target_from_close(row.symbol, row.close, w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if p.gate and not trend_on(history, data_date, GATE):
            return ()
        if not model_ready(data_date, p.train_start, p.min_train_months, p.horizon):
            return _bench(history, data_date)
        return self._pick(factor_rows(history, members, data_date, SCREEN), p)

    def prepare(self, history: Mapping[str, History]) -> ControlPrepared:
        return ControlPrepared(MappingProxyType(dict(history)), prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if not isinstance(prepared, ControlPrepared):
            raise TypeError(f"prepared must be ControlPrepared, got {type(prepared).__name__}")
        if p.gate and not trend_on(prepared.history, data_date, GATE):
            return ()
        if not model_ready(data_date, p.train_start, p.min_train_months, p.horizon):
            return _bench(prepared.history, data_date)
        return self._pick(prepared.factor.rows_on(members, data_date, SCREEN), p)


SIZED_DV = SizedVolumeBook()


# --------------------------------------------------------------------------- the method


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0132-{suffix}", family="M0132", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0132",
    name="Learn the fall, not the pick: a model that forecasts the next quarter's drop and sizes the book by it",
    family="model-sized-exposure",
    source_kind="paper",
    source_ref=(
        "Moreira & Muir (2017), Volatility-Managed Portfolios, Journal of Finance 72(4); "
        "handover 2026-10-13 (measure the constraint), section 2 item 2"
    ),
    parent_id=None,
    hypothesis=(
        "This lab's own record says the constraint that binds is the fall, not the pick: of 394 "
        "dev trials with a recorded return, 256 (65%) beat SPY total return but only 92 (23%) keep "
        "the worst fall at or under 20%, and all four spent test looks failed on return, not on "
        "drawdown. A two-thirds dev hit rate that vanishes out of sample is the signature of "
        "selection. Against that the lab has exactly one risk control, the SPY 200-day switch, and "
        "nothing has improved on it. THE QUESTION: can a learned forecast of the coming fall size "
        "a book better than that switch does? THE LABEL is the forward fall AS A LEVEL -- the "
        "worst peak-to-trough drop over the next 63 NYSE sessions, one quarter, in fractions -- "
        "not the next month's return rank and not a rank of the fall either. That distinction is "
        "the method: every feature below is rank-normalised within its date, and a label ranked "
        "the same way would leave the forecasts near-identical on every date by construction, so "
        "in October 2008, when every name is about to fall, the label could not say 'all of them' "
        "even in principle. THE HEAD turns the forecast into exposure, the share of the book that "
        "is held, with the remainder in cash, and it reads a MARKET-LEVEL quantity to do it: the "
        "date's cross-sectional MEAN forecast fall is located in the model's own training "
        "distribution of date-level means, and the book keeps the share of its slots that the date "
        "is calmer than -- in whole slots, each at a fixed weight, never renormalised onto the "
        "survivors. A date calmer than every training date is a full book, a date worse than all "
        "of them is entirely cash, the median date is half. NO NUMBER IN THAT LADDER WAS CHOSEN: "
        "it is the model's own in-sample distribution, so nothing in the head was read off the dev "
        "window. The machinery is M0130's: scikit-learn histogram "
        "gradient-boosted trees refitted once a year at the last session of each year, on every "
        "month-end sample since January 1996 whose label had already been read by then (an "
        "expanding window; nothing dated after the decision date is ever read), on the same seven "
        "features the lab already computes, each rank-normalised per date: 12-1 momentum, 60-day "
        "volatility, 20-day dollar volume, M0007-N20-RAW's residual momentum, distance from the "
        "52-week high, M0070's dividend-raise event and the trailing dividend yield -- PLUS THREE "
        "UN-NORMALISED MARKET-LEVEL COLUMNS, without which a level label would buy nothing: the "
        "market's distance below its trailing one-year high, its realised volatility over the last "
        "sixty sessions, and the spread of the day's own momentum across the cross-section. Each "
        "of those three is one number for the whole date, repeated down the rows, so none of them "
        "can change which names the model prefers -- only how far the whole date's forecast moves, "
        "which is exactly the level the head reads. THE NAMES ARE "
        "HELD FIXED and are not the question: every variant, model and control alike, holds the "
        "twenty screen-eligible index members with the largest 20-day dollar volume, equal weight. "
        "Dollar volume forecasts nothing, so the only thing that differs between variants is how "
        "much of that same book is held, and every paired difference below is the sizing alone. "
        "BEFORE THE FIRST MODEL every variant holds SPY. With a quarter-long label and 35 required "
        "labelled month-ends the first refit with enough history is 1999-12-31, so the book is SPY "
        "through 1999 in all five; the rule is calendar-only and shared with the controls, which "
        "have no model, so the pre-model era is identical everywhere and cancels out. FIVE "
        "VARIANTS, THE ONLY SETTINGS EVER TRIED: no hyperparameter was tuned on the dev window off "
        "the books, and none will be; a change after a result is a new method. The base tree is "
        "Strategy B's pre-registered setting (learning rate 0.05, 300 trees, 15 leaves, at least "
        "200 samples per leaf, L2 1.0), fixed 2026-10-03 for a different book and never searched; "
        "the regularised tree (100 trees, 7 leaves, 1,000 per leaf, L2 10) is M0130's one fixed "
        "alternative re-used verbatim. FALL20 is the model sizing the book; FALL20-REG is the "
        "regularised tree doing the same; FALL20-GATE is the base model also behind the SPY "
        "200-day switch; GATE20 is the CONTROL in which that switch alone sizes the same twenty "
        "names; ON20 is the CONTROL that is always fully invested, with no risk control at all. "
        "WHAT EACH DIFFERENCE ISOLATES: GATE20 minus ON20 is what the lab's existing control is "
        "worth on this exact book; FALL20 minus ON20 is what the learned forecast adds over no "
        "control; FALL20 minus GATE20 is the question itself; FALL20-GATE minus GATE20 is whether "
        "the model sees anything the switch has not already taken; FALL20-REG minus FALL20 is "
        "whether any of it is model capacity rather than signal. WHAT COUNTS AS THE MODEL ADDING "
        "SOMETHING, fixed now: FALL20's worst fall over the model era is at least 5 percentage "
        "points shallower than GATE20's AND its funded return is no more than 2 points a year "
        "behind GATE20's -- a control that only costs return is not an improvement, because the "
        "switch already does that -- AND FALL20 beats ON20 on MAR. WHAT COUNTS AS A METHOD: a "
        "variant clears every design section 1 bar at DSR >= 0.90 at the lab's N, the worst fall "
        "at or under 20% included. IDLE CASH EARNS NOTHING in these rules, which is the version "
        "the owner can actually trade; it biases every exposure-reducing variant downward, and the "
        "FALL20-minus-GATE20 comparison absorbs nearly all of that because GATE20 sits in cash "
        "too. NO VARIANT IS PROMOTED in this run whatever it shows: the test window is not touched."
    ),
    expected_failure=(
        "Most likely the model's exposure ladder turns out to be a slow volatility target wearing "
        "a new name. Realised volatility is the most persistent of the seven features and is "
        "already one of them, and a forward-fall label over a quarter is largely a volatility "
        "label, so the forecast will probably track trailing volatility closely enough that the "
        "book cuts exposure when volatility is already high -- which is after the fall has begun, "
        "not before it. The lab has priced volatility targets before and they did not clear the "
        "20% bar, and two of the three market-level columns -- the market's own realised "
        "volatility, and its distance below its one-year high -- are precisely the inputs a slow "
        "volatility target would use, so the head has every opportunity to rediscover one. Second, "
        "the level may be too coarse to be worth reading: the exposure ladder is driven by a "
        "single number a date, the cross-sectional mean forecast, located in a training "
        "distribution of at most a couple of hundred date-level means, so the ladder's resolution "
        "is one slot per few percentiles and the book may end up moving between full and nearly "
        "full on almost every date. If the realised exposure turns out to sit in a narrow band -- "
        "say between eighteen and twenty of the twenty slots on nine dates in ten -- then FALL20 "
        "will be nearly indistinguishable from ON20 whatever the forecast said, and the honest "
        "verdict is that the question was asked too quietly to hear the answer. (The flat-exposure "
        "failure this method was originally at risk of -- a label ranked within each date, which "
        "cannot encode a market-wide fall at all -- was removed before pre-registration: the label "
        "is a level and the feature matrix carries un-normalised market columns. That the exposure "
        "moves at all, and falls in 2008, was measured on the dev window before this file was "
        "committed. What was NOT measured, and is the open risk, is whether it moves ENOUGH and in "
        "the right years.) Third, the SPY 200-day switch is a very hard thing to beat on this window for a "
        "reason that is not skill: it caught 2008, the one year that dominates every whole-window "
        "drawdown number, and the lab has already measured that nearly all of the switch's "
        "whole-window value is that single year and that it has been a drag since 2009. So GATE20 "
        "is likely to win the whole window on the strength of 2008 and lose 2009-2015, and a model "
        "that is better than it after 2009 may still look worse over the full record. Fourth, the "
        "fall is broader than one crash: of the 302 dev trials that breached 20%, the worst year "
        "is 2008 for 103 of them but 2011 for 51 and 2015 for 50, so a forecast that only learns "
        "the shape of 2008 will not keep the fall under 20% and no variant here will clear design "
        "section 1. Fifth, cutting exposure costs return in a window SPY roughly quadrupled over, "
        "and with idle cash earning nothing every reduction is a pure drag on the return side of "
        "every bar; the monthly decision cadence also means the book cannot step aside faster than "
        "once a month, which was late in 2008 for every lab book that used the switch. Sixth, the "
        "training set inherits the store's survivorship -- about half of the index members ever "
        "listed are missing, mostly the ones that died -- and a fall model trained on survivors' "
        "histories has systematically seen fewer catastrophic falls than really happened, which "
        "should make it optimistic exactly where it matters most. Seventh, twenty years of monthly "
        "cross-sections is a small and heavily correlated sample for a learner, and a quarter-long "
        "label makes neighbouring month-ends overlap by two thirds, so the effective sample is "
        "roughly a third of the row count and the DSR at the lab's N may not separate a real "
        "sizing skill from luck even if the returns look good. Finally, the regularised arm is "
        "expected to sit between the base model and the controls, and if it does not -- if the "
        "regularised tree is clearly better -- that is evidence the base tree was overfitting the "
        "label and the right reading is that neither setting found anything."
    ),
    candidates=(
        _v("FALL20", FALL_BOOK, FallBookParams(BASE),
           "The fall model sizes a twenty-name dollar-volume book, base tree"),
        _v("FALL20-REG", FALL_BOOK, FallBookParams(REG),
           "The same book sized by the regularised tree (100 trees, 7 leaves, 1000 per leaf, L2 10)"),
        _v("FALL20-GATE", FALL_BOOK, FallBookParams(BASE, gate=True),
           "The base model's sizing behind the lab's standing SPY 200-day switch as well"),
        _v("GATE20", SIZED_DV, ControlParams(gate=True),
           "Control: the same twenty names sized only by the SPY 200-day switch, no model"),
        _v("ON20", SIZED_DV, ControlParams(),
           "Control: the same twenty names always fully invested, no risk control at all"),
    ),
    seen_keys=(
        "concept:forward-drawdown-label",
        "concept:model-sized-exposure",
        "concept:learned-risk-control",
        "concept:market-level-exposure-ladder",
        "concept:walk-forward-annual-refit",
    ),
)
```

**Impact:** nothing runs yet. The file is on disk and uncommitted, which `registry_problem` would
refuse — correct, until Step 7.

---

### Step 5: Lint and run the whole suite. The new file must pass the method battery BEFORE the commit.

**File:** none.
**Change:** none.

```bash
docker start seer-pg 2>/dev/null || true

/home/miftah/seer/engine/.venv/bin/ruff check /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine

cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

Quote the **skip count beside the pass count** in the commit body. Without `PG_TEST_URL` 385 tests
skip silently; without `PYTHONPATH` pytest imports the main checkout and tests the wrong code.

The new file must pass all of `engine/tests/test_lab_methods.py`:

| Test | What it proves about this file |
|---|---|
| `test_method_source_is_pure` | no `time`/`random`/`os`/`sqlite3`/`subprocess` import, no `now`/`today`/`random` attribute, no `print`/`open`/`eval` call, and no import of `seer_engine.research` or `seer_engine.lab.store` |
| `test_candidate_runs_a_smoke_window` (x5) | each of the five candidates runs `dev.run_candidate` to `DEV_END` on the 473-bar smoke fixture |
| `test_allocator_contract` (x5) | `FALL_BOOK` is `MarketAware`, so it must target **nothing** on the history-only path (`assert nonempty == 0`); `SIZED_DV` is **not** `MarketAware`, so its probes must return targets (`assert nonempty > 0`), plus the P4 identity and the no-look-ahead probes |
| `test_allocator_ids_are_unique_across_methods` | `"M0132"` and `"M0132-DV"` are not claimed by any registry or lab allocator |
| `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` | skips this file until it has run; must stay green for every other method |
| `test_every_recorded_configuration_still_digests_to_its_recorded_digest` | **the tripwire**: M0130's six recorded digests must not have moved. If phase 2 touched anything M0130's params import, this goes red here and is phase 2's bug, not this phase's — report, do not patch |

**Lookback:** `FALL_BOOK.lookback` is phase 2's `FALL_FEATURE_LOOKBACK`, and `SIZED_DV.lookback` is
the same constant, or `max(FALL_FEATURE_LOOKBACK, factor_lookback(GATE))` with the gate on. Phase 2
proved the constant is `max(FEATURE_LOOKBACK, MARKET_HIGH_N, MARKET_VOL_N + 1) = max(401, 252, 61)
= 401` — **the three market-level columns add no reach** — so both stay at or under the smoke
fixture's **473 bars**. If that constant has moved past 473,
`test_candidate_runs_a_smoke_window` fails here — report it to phase 2, do not work around it.

**Impact:** a red suite here means the method file is not ready to be pre-registered. Fix the file
(it is this phase's), or report (if it is phase 2's or phase 1's). Never commit a red tree.

---

### Step 6: Record N and the lab's counters on the near side of the run.

**File:** none.
**Change:** none. These numbers go in the write-up and the commit body.

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
from seer_engine.lab import npolicy, store
conn = store.connect_readonly()
g = store.gate(conn)
print("policy            ", store.DSR_POLICY, " DSR_MIN", store.DSR_MIN)
print("gate N (before)   ", g.n)
print("dev_method_count  ", npolicy.dev_method_count(conn))
print("dev_trial_count   ", store.dev_trial_count(conn))
print("test_looks        ", store.test_looks(conn))
print("insights          ", conn.execute("SELECT count(*) FROM insights").fetchone()[0])
print("pending_gate N    ", store.pending_gate(conn, "M0132", 5).n)
PY
```

**Measured 2026-10-13 (read-only, before any phase landed):** `dev_trial_count` = **394**,
`test_looks` = **4**, distinct dev methods = **80**.

**Predicted after the run:** `dev_trial_count` = 399 (+5), distinct dev methods = 81,
`test_looks` = **4, unchanged**. Under `DSR_POLICY = "methods"` the lab's N moves by exactly **one
method**, not by one per hyperparameter setting — and that +1 is applied **retroactively to every
recorded trial's published verdict**. That is the real price of this run, and it is why the variant
list is five and is fixed: **no setting may be tuned on the dev window off the books, and a change
after a result is a new method, not a revision of this one.**

**Impact:** none; this is the "before" half of an invariant check.

---

### Step 7: The pre-registration commit — the method file ALONE, before any run.

**File:** `engine/src/seer_engine/lab/methods/m0132_fall_sized_book.py`
**Change:** commit it. **This commit IS the pre-registration.** `hypothesis` and
`expected_failure` are frozen by it and must already be the final prose from Step 4.

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
git status --short                       # see what peers have in flight; change nothing of theirs
git add -- engine/src/seer_engine/lab/methods/m0132_fall_sized_book.py
git commit -m "lab: M0132 pre-registered — a model that sizes the book by the fall it forecasts, not the names it picks

Five variants, fixed before any result: three model arms (base tree, regularised tree,
and the base tree also behind the SPY 200-day switch) and two controls on the same twenty
dollar-volume names (the switch alone, and always fully invested). Price and dividend
features only — no fundamentals variant.

Suite: <PASS> passed, <SKIP> skipped (PG_TEST_URL set, PYTHONPATH on the worktree).
Lab before the run: N = 80 methods, 394 dev trials, 4 test looks.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  -- engine/src/seer_engine/lab/methods/m0132_fall_sized_book.py

git show --stat HEAD                     # MUST list exactly the one file
```

**`git reset --hard`, `git clean`, `git checkout .` and every bare-path form are BANNED in this
worktree and its git index, which are shared by concurrent phase sessions.** Say that verbatim in
any subagent prompt you write for this phase, and write the `Co-Authored-By` trailer out verbatim
rather than letting a subagent substitute its own model name.

**Why before the run:** `runner.preflight` calls `registry_problem(path)`, which runs
`git status --porcelain -- <file>` and `git ls-files --error-unmatch -- <file>` in the file's own
directory. An uncommitted, dirty or untracked file is refused. A **feature-branch** commit
satisfies it; the file does not have to be on `main`.

**Impact:** the hypothesis is now frozen. Editing it afterwards is editing a pre-registration.

---

### Step 8: The run.

**File:** none (the database is appended to).
**Change:** five dev trials, one method row, one `method_folds` row.

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
echo "SEER_LAB_DB=${SEER_LAB_DB:-<unset: the worktree's own lab/lab.sqlite>}"
git status --short                       # must be clean of your own files before the run

PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine -v lab run M0132 \
  --store /home/miftah/seer/engine/.research 2>&1 | tee "$SCRATCHPAD/m0132-run.log"
echo "exit: $?"
```

**`--store /home/miftah/seer/engine/.research` is not optional.** `engine/.research/` does not
exist in this worktree. **Do not rebuild a store** — it is ~30 minutes plus a yfinance crawl for
nothing, and `hardgate.pin_dev_store` would refuse the rebuilt store's price fingerprint anyway.
Loading from the main checkout was measured at about **13 seconds**.

**There is no useful `--dry-run` on this path.** `lab run` has no `--dry-run` flag of its own, and
`_promote`'s docstring states the house rule plainly: "Like every other `lab` subcommand, the
global `--dry-run` is ignored." So the refusal ladder is the dry run, and Steps 1-7 exist to clear
every rung of it before the backtest is paid for. In order, `_run` refuses:

1. `research.declared_purpose(args.store)` — a survivorship-check store, refused before anything is
   discovered or loaded. `engine/.research` is the dev store and is unmarked; it passes.
2. `method.discover()` — no method file for the id, or a module number that disagrees with
   `METHOD.id` (Step 2).
3. `runner.preflight` — `registry_problem` (Step 7), `real_cost_problem` (satisfied by
   `MONTHLY_HOLD_FRAC_GOTRADE_TBAND`), "this method already ran" (M0132 is new), a missing parent
   (`parent_id` is None), and any candidate whose `config_digest` already has a dev trial (the two
   allocator ids are new, so no digest can collide).
4. `research.DEV_END == dev.DEV_END` — unchanged by this set.
5. `hardgate.pin_dev_store(conn, data.price_fingerprint)` — the store's prices must be the
   benchmark's. **No flag skips this.** A rebuilt store is refused here; the main checkout's store
   is the pinned one.
6. `runner.preflight_data` — the fundamentals coverage floor. Never engaged: every variant's
   `market_fields` is `("dividends",)` or `()`, so **no `--allow-coverage` is passed, ever**.

Exit code **2** means the lab refused: read the message, fix the cause, and only then re-run. Exit
**1** is an error. Exit **0** means the method id is spent.

**Run it in the foreground.** Five variants with yearly refits over twenty years; budget up to an
hour. Do not background it and do not interrupt it mid-transaction.

**What the run prints and you must capture from `$SCRATCHPAD/m0132-run.log`:**
- `_show(M0132)` — the five trials, their returns, falls, profit factors, DSR and verdicts;
- phase 1's **fold verdict** line — quote it verbatim in the write-up (an exit criterion);
- `Lab N (dev trials) is now 399; test-window looks used: 4`.

**Impact:** irreversible. `trials`, `methods` and `insights` are append-only by trigger.

---

### Step 9: Verify the record, then journal, stage and commit the database.

**File:** `lab/lab.sqlite`, `web/data/lab.json`
**Change:** one insight row; both files staged by `lab stage` and committed together.

**9a — the far-side invariants.**

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
from seer_engine.lab import npolicy, store
conn = store.connect_readonly()
print("gate N (after)   ", store.gate(conn).n)
print("dev_method_count ", npolicy.dev_method_count(conn))   # expect 81
print("dev_trial_count  ", store.dev_trial_count(conn))      # expect 399
print("test_looks       ", store.test_looks(conn))           # MUST still be 4
ns = [r[0] for r in conn.execute("SELECT n FROM trials ORDER BY n")]
print("trial n contiguous:", ns == list(range(ns[0], ns[0] + len(ns))), "max n =", ns[-1])
for r in conn.execute("SELECT candidate_id, config_digest FROM trials WHERE method_id='M0132' ORDER BY n"):
    print(" ", r[0], r[1][:12])
print("folds row:", conn.execute("SELECT * FROM method_folds WHERE method_id='M0132'").fetchall())
PY

git status --short docs/lab/             # MUST be empty
```

`store.test_looks(conn)` must still read **4** and `git status --short docs/lab/` must be empty —
this phase never promotes and never touches the test window.

**On the `insights` count: read it, never assert an absolute.** Phase 3 appends one correcting
insight before this phase runs, and a peer session may append others, so the only invariant here is
*exactly one higher than whatever this phase read on its near side* — take that baseline in Step 6
and compare it in Step 9. Phase 3 owns its row and this phase owns only its own; neither asserts
anything about the other's id. `dev_trial_count` (394 → 399) and `test_looks` (4, unchanged) are
this phase's counts and those are the ones to pin.

**9b — the journal entry, in plain language.** No ids, digests, code identifiers, "DSR" or
"walk-forward". Write the body to a file first so the prose is reviewable:

```bash
cat > "$SCRATCHPAD/m0132-insight.txt" <<'TXT'
<Two or three short paragraphs in the owner's language. The shape, filled in from the result:

 - What was asked: whether a model that tries to predict how far a basket of big, heavily traded
   companies will drop over the next three months can decide how much of that basket to own --
   better than the one brake this lab already has, which is simply to stop buying when the market
   is below its long-term average.
 - What happened, honestly, whichever way it fell. If the model's sizing beat the brake, say by
   how much and in which stretches. If it did not, say that plainly and say whether it was close.
 - What this does and does not license. It tested one way of forecasting a fall, from signals the
   lab already had, on big companies, long only, after real fees, with cash earning nothing. It
   does not settle whether forecasting the fall is the right idea.>
TXT

PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab insight \
  --kind observation --method M0132 \
  --title "<a plain-language title, no ids>" \
  --file "$SCRATCHPAD/m0132-insight.txt"
```

**9c — stage and commit the database with NO pathspec.**

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
git diff --cached --name-only            # MUST be empty before lab stage, or a peer's work is swept
git status --short

PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab stage

git diff --cached --name-only            # MUST be exactly lab/lab.sqlite and web/data/lab.json
git commit -m "lab: M0132 <rejected|dev-eligible> (<plain reason, no ids or digests>)

<One or two plain sentences: what the model was asked to do and what it did.>

Five dev trials, one method id. Lab N moved 80 -> 81 methods (394 -> 399 dev trials);
test-window looks 4, unchanged. Fold verdict: <quote the line lab run printed>.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

git show --stat HEAD                     # exactly two files
```

**`git commit -- <paths>` re-reads the working tree and defeats `lab stage`** — the staged
`lab.json` must stay the export of the staged `lab.sqlite`, which only a bare `git commit` of the
index guarantees. This is the one commit in this plan set that carries no pathspec, and it is why
`git diff --cached --name-only` is checked on both sides of `lab stage`.

If the method is rejected, the commit message says so in the house style:
`lab: M0132 rejected (<plain reason>)`.

**Impact:** CI checks `lab.sqlite` and `web/data/lab.json` agree row for row; staging them together
is what makes that pass.

---

### Step 10: The write-up.

**File:** `docs/backtests/2026-10-13-learn-the-fall.md` (new)
**Change:** the house-format write-up, in plain language, stating the result against the
pre-registered hypothesis **and** the expected failure, **both ways round**.

**Skeleton** (follow `docs/backtests/2026-10-12-exposure-diagnostic.md` for tone and header shape):

```markdown
# Learning the fall instead of the pick

**Measured:** 2026-10-13 · **Window:** 1996-01-03 → 2015-10-16 (the lab's development window)
**Research store:** `<fingerprint[:12]>` (dev, unmarked) · **Prices:** `<price fingerprint[:12]>`
**Command:** `lab run M0132 --store engine/.research`

## The short answer

<Three to six sentences, plain language, no ids. Did a learned forecast of the coming fall size
the book better than simply stopping when the market is below its long-term average? Say it
straight, whichever way it fell, and give the two or three numbers that carry the answer.>

## Why this was measured

<The lab's own record: two thirds of everything beats the market on the development window, but
under a quarter keeps the fall at or under a fifth, and all four out-of-sample looks failed on
return rather than on the fall. The lab has one brake and it has never been improved on. So the
model was pointed at how much to own rather than at what to own.>

## What was run

<The five arms in a table, in plain words — three model arms and two comparison books. Say that
every arm holds the same twenty companies, chosen by how heavily they are traded, which forecasts
nothing, so the only thing that differs is how much of the book is held. Say that every arm holds
the market index until the end of 1999, because there is nothing to learn from before then.>

| Arm | How much of the book is held |
|---|---|
| … | … |

## What each comparison isolates

<The five paired differences from the plan, in plain language. This is the section that makes the
result readable: the brake against nothing, the model against nothing, and the model against the
brake — which is the question.>

## The result

<The table of returns, worst falls, profit factors and funded returns, plus the fold verdict line
`lab run` printed, quoted verbatim. Every number reproducible from the recorded trials.>

## Against the hypothesis

<Quote the pre-registered success criterion — a fall at least five points shallower than the
brake's with no more than two points a year of return given up, and better MAR than the
always-invested book — and say whether it was met. Do not soften it either way.>

## Against the expected failure

<Walk the eight expected failure modes and say which actually happened: the volatility-target
look-alike, the exposure ladder being too coarse to matter (print the actual distribution of how
much of the book was held, by year — this is the one the reader will want), the brake winning on
2008 alone, the fall being broader than one crash, the cost of sitting in cash with no interest,
survivorship making the model optimistic, the overlapping quarter-long labels shrinking the
effective sample, and the regularised arm landing outside the model-to-control range. Name the ones
that did NOT happen too — an expected failure that did not occur is a finding.>

## What this does and does not license

<Narrow, honest. One label, one model family, one universe, long only, after real fees, idle cash
earning nothing. What the next question should be.>
```

**Commit:**

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
git add -- docs/backtests/2026-10-13-learn-the-fall.md
git commit -m "docs: learning the fall instead of the pick — <one-line verdict>

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  -- docs/backtests/2026-10-13-learn-the-fall.md
git show --stat HEAD
```

**Impact:** documentation only.

---

### Step 11: Final green.

```bash
docker start seer-pg 2>/dev/null || true
/home/miftah/seer/engine/.venv/bin/ruff check /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

`test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` now covers M0132: the file on disk
must hash to the `source_sha` the run recorded. If it goes red, the file was edited after the run —
restore it from the pre-registration commit (`git checkout <sha> -- <the one file>`, which is a
pathspec checkout of a single file and **not** the banned bare `git checkout .`).

---

## Verification

**Build:** `/home/miftah/seer/engine/.venv/bin/ruff check /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine`
(CI lint is bugs only: E9 and F, minus F401)

**Tests:**
```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q
```
Quote the **skip count beside the pass count** in every commit body. `docker start seer-pg` if the
container is down; CI fails a run where the DB tests skip.

**Manual check:**
- `lab show M0132` prints five trials, each with its moments, funding and provenance, plus the
  recorded fold verdict.
- `sqlite3 'file:lab/lab.sqlite?mode=ro' "SELECT count(*) FROM method_folds WHERE method_id='M0132';"`
  reads **1**.
- `git log --oneline -4` shows, oldest first: the pre-registration commit (one file), the database
  commit (two files), the write-up commit (one file).

**Exit criteria:**
1. The method id came from `lab next-id` at run time; the file's module number equals `METHOD.id`.
2. The method file was committed **in its own commit, before** `lab run`, and the run was not
   re-run because of an uncommitted-file refusal.
3. Every variant ranks on price and dividend features only; `--allow-coverage` was never passed;
   no variant names a fundamentals allocator (there is none to name — D14).
3a. **The pre-registration describes the method that was built (D13).** The `hypothesis` says the
   label is the forward fall **as a level**, names the three un-normalised market-level columns, and
   describes the head as locating the date's cross-sectional mean forecast in the model's own
   training distribution of date-level means. It does **not** say "rank-normalised label" anywhere,
   and it pre-registers no exposure ladder of this phase's own choosing.
3b. **Step 3's exposure re-check passed and agrees with phase 2's M5b**, and both outputs are
   quoted in the write-up.
4. `lab run` recorded one trial per variant with its `trial_provenance`, `trial_moments` and
   `trial_funding` rows, plus one `method_folds` row, and the printed fold verdict is quoted in the
   write-up.
5. The lab's N moved by exactly one method: `store.gate(conn).n` and `npolicy.dev_method_count`
   read on both sides and recorded (80 → 81; 394 → 399 dev trials).
6. `store.test_looks(conn)` is unchanged at **4** and `git status --short docs/lab/` is empty.
7. Trial `n` is contiguous; `lab stage` ran; `lab/lab.sqlite` and `web/data/lab.json` were
   committed together with **no pathspec**; CI's row-for-row check passes.
8. The write-up and the journal entry are in plain language — no ids, digests or code — and state
   the result against the pre-registered hypothesis **and** the expected failure, both ways round,
   whichever way it fell. If rejected: `lab: M0132 rejected (plain reason)`.
9. `ruff` clean, suite green, skip count quoted.

---

## Assumptions

- **Phase 1 has landed** and `lab/lab.sqlite` is at schema v7 with a `method_folds` table. Today it
  is at v6 with no such table (measured read-only). Step 1 is the gate.
- **Phase 2 has landed** `FallSizeParams` and `FALL_SIZE` in `lab/tree_rank.py`, with
  `TreeRankParams`, `TreeRankAllocator`, `TREE_RANK`, `TREE_RANK_FUND`, `build_section`, `Section`,
  `rank_columns` and `PRICE_FEATURES` byte-identical, so M0130's recorded `config_digest`s have not
  moved. **The names are settled, not assumed** (Step 2b): the reconciler took them from phase 2's
  Interface Contract. The book-size field is `slots`, not `top_n`.
- **Phase 2's `FallSizeParams` mirrors `TreeRankParams`' field names** for `horizon`,
  `train_start`, `min_train_months`, `max_iter`, `max_leaf_nodes`, `min_samples_leaf` and `l2`, and
  carries an `as_dict() -> dict[str, str]`.
- **Phase 2's label is the RAW forward fall, a level, with no `rank01` applied** (D13), and its
  feature matrix carries three un-normalised market-level columns beside the ranker's seven. The
  `hypothesis` in Step 4 describes exactly that; if the landed code disagrees, **stop and report** —
  a pre-registration that does not describe the method is worse than no pre-registration.
- **Phase 2's sizing head reads a market-level quantity and can move exposure over time.** Phase 2
  measured this on the real store as its own exit criterion **M5b** and fails itself if it cannot;
  Step 3 re-measures before anything is committed and stops this phase if it cannot.
- **Phase 2 exports NO `FALL_SIZE_FUND`** (D14). Importing one is an `ImportError`.
- **`FALL_FEATURE_LOOKBACK` is 401 and the market columns added no reach**, so the fall path is
  inside the smoke fixture's 473 bars. If it is not,
  `test_candidate_runs_a_smoke_window` fails in Step 5 — report to phase 2.
- **Phase 3 has landed** its correcting insight, so this phase's insight is strictly newer and the
  two read in the right order on `/sera`.
- **`m0130_tree_ranker.model_ready` is importable and unchanged.** It is frozen against its
  recorded sha, and no phase in this set touches a method file other than the new one.
- `lab next-id` prints **M0132**. Verified read-only: the highest `methods` row is `M0131`.
- The run uses the worktree's own `lab/lab.sqlite` unless `SEER_LAB_DB` points elsewhere; Step 8
  prints which.

---

## Handoffs

- **Phase 2 (R2) — the cross-phase conflict this phase raised is RESOLVED (D13).** The draft of
  this plan flagged that a per-date rank label on top of per-date rank features leaves the
  prediction distribution near-identical on every decision date, so no head could size the book and
  R2 would not actually be tested. The reconciler upheld it: phase 2's fall label is now the raw
  level, its feature matrix carries three un-normalised market-level columns, its head reads the
  date's cross-sectional mean against the model's own training distribution, and **the exposure
  measurement moved into phase 2 as its own exit criterion (M5b)** so a flat head fails the cheap
  phase rather than the irreversible one. Step 3 here is the deliberate re-check. Nothing is left
  open; if the landed code disagrees with any of it, stop and report rather than improvising.
- **Phase 1 (R1) — the fold verdict's wording.** This phase only quotes what `lab run` prints. If
  the printed verdict is not a single quotable line, that is phase 1's output format, not this
  phase's write-up.
- **Any bug this run exposes is REPORTED, never patched from here.** That is a hard stop: patching
  engine code from a lab-operation phase is how a run stops being the thing that was
  pre-registered. Write it up, tell the coordinator, and let the owning phase or a later one fix
  it. (M0130's own run exposed exactly such a bug and it was fixed in a separate commit,
  `450a5ea lab: tree ranker fits an all-blank feature column as unsplittable`, before the run.)
- **Promotion, the walk-forward promote gate and the test window are out of scope and stay out.**
  Whatever this method shows, no variant is promoted in this set. If a variant clears every §1 bar,
  that is a finding for the next session to act on, with `lab promote` and its hard gate in front
  of it.
- **`.workflows/todos.md` and the plan index tick** belong to the coordinator / completion handler,
  not to this phase. The orchestration `PLAN.md` lives on `main`, not on this branch.
- **A sixth variant, a second label (realised downside volatility rather than drawdown), a weekly
  cadence, or a T-bill-crediting rule set** are all real follow-up questions and all of them are
  **new methods**, not revisions of this one (D10). Record them as `lab idea` rows if they are
  worth keeping; do not add them to this file after a result.

---

## Rollback

**This phase cannot be rolled back, by design.** `trials`, `methods` and `insights` are append-only
by SQLite trigger; the method id is spent the moment `lab run` exits 0; and under
`DSR_POLICY = "methods"` the +1 to N is applied retroactively to every recorded trial's published
verdict. An idea that ran is counted. That is the lab's design, not a defect.

What *can* be undone, and how:

| Artefact | How to undo |
|---|---|
| The write-up commit | `git revert <sha>` — documentation only |
| The method file, **before** `lab run` only | `git revert <the pre-registration sha>`, then delete the file. After the run it must stay: `store.latest_source_sha` pins it and `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` goes red without it |
| A journal entry | **Never deleted.** Insights are append-only; a correction is a *newer* entry, exactly as phase 3 corrects insight 217 |
| The database commit | Reverting the commit does not un-run the method — it only de-syncs the committed file from the lab the run actually wrote. Do not revert it on its own |

**`git reset --hard`, `git clean` and `git checkout .` are banned in this worktree**, which shares
one git index with every concurrent phase session. The one permitted checkout is a single-file
pathspec restore of this phase's own method file from its own commit.

The mitigation for this phase is entirely **in front of** the run: Step 1 (dependencies), Step 3
(the exposure measurement that can stop the phase for free), Step 3b (the kin measurement), Step 5
(a green suite), Step 6 (N recorded on the near side) and Step 7 (the pre-registration commit that
freezes the hypothesis). Every one of them costs minutes; the method id cannot be given back.

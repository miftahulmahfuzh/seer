# Phase 7: Tree-ranker method: pre-register and run on the dev window

**Plan set:** `MEASURE_THEN_LEARN_PLAN.md`
**Analysis:** `20261012-205553-M7T1_code_analyzer.md`
**Satisfies:** R5. One pre-registered gradient-boosted-tree cross-sectional ranker, run on the dev window.
**Depends on:** Phases 3, 5 and 6. Phases 1 and 2 come in through 3. Phase 4 supplies `SEER_SV_STORE` and a current survivorship-check store, which phase 5 also needs.
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab/methods` (one new method file), plus lab data (`lab/lab.sqlite`, `web/data/lab.json` in the main checkout)

---

## Goal

After this phase the lab holds one new method in the family `stock-ml-ranker`. It is pre-registered
by a commit that contains only its method file. It wraps phase 6's walk-forward tree allocator in
six fixed variants: four price-only trees, one tree that also reads fundamentals, and one
signal-free control book of identical shape. All six run on the dev window (to 2015-10-16) on the
target-band, real-fee, fractional, owner-funded tape. The variants are survivorship-checked,
analysed in plain words, journaled and staged. The test window is never touched, and nothing is
promoted, whatever the result.

## Decisions taken in this phase (implementer: do not re-litigate)

| Fork | Chosen | Why |
|---|---|---|
| Control | **a signal-free book of identical shape**: the 20 screen-eligible members with the largest 20-day dollar volume, equal weight. Same screen (`tree_rank.SCREEN`), same 401-bar lookback, same rules, same "too early for a model" clock, so it is scored on exactly the same sessions and holds exactly what the trees hold before their first model. **Not** plain 12-1 momentum. | (1) "Does the model add anything" is answered by the same book picked without the model. (2) A momentum control would very likely make the **whole method** behavioural kin of the four test-failed momentum books. `hardgate.behavioural_kin` (D14) compares **every** dev variant of a method against each test-failed tested curve at a residual correlation of ≥ 0.85, so a single momentum variant would make every tree variant unpromotable forever. The tree-vs-momentum comparison is still made in the note, against the lab's recorded real-fee momentum books, without spending a variant on it. (3) It is the same kind of control phase 5 and M0120 use (most-traded members), so the lab's "picking or shape?" answers stay comparable. |
| Before the first model | **hold SPY at full weight** (behind the gate in the gated variant), in every variant including the control | Phase 6's first model is the 1998-12-31 refit, and a member book's dev window opens in early 1996 (`dev.MEMBERSHIP_START`). Three years in cash during SPY's 1996–98 run would decide "beats SPY" by a data-availability artefact, not by the model. Holding the yardstick while there is nothing to learn from is neutral against the yardstick. The 1996–98 stretch is then the same in all six variants, so every paired difference is the model alone. The lookback cannot delay the window (phase 6 Handoff: `labkit.smoke_market` has 473 SPY bars, so lookback must stay ≤ 473). |
| "Is a model ready on d?" | a pure calendar rule in the method file (`model_ready`), built from phase 6's `anchor_for`, `month_ends` and `label_end`: ready iff the refit at `anchor_for(d)` has ≥ `min_train_months` month-ends whose label was read by the anchor | The control has no model to ask, and both kinds of variant must share one clock. Step 4 checks on the real dev store that this rule agrees with `TreeRankPrepared.model_on(d, p) is not None` on every month-end 1996–2015, **before** the pre-registration commit. |
| Fundamentals | **one** `price+fund` variant (PF20), paired with P20, run under `lab run --allow-coverage 0.31` | Measured 2026-10-12 on the main checkout's dev store (read only, see Step 1): the panel can rank ≥ 20 symbols on 75 of 238 monthly samples, **0.3151** of the dev window. Every year 1996–2008 is 0/12, then 2009 5/12, and 2010–2015 are fully covered. Before 2009 the four fundamental columns are entirely NaN, so a tree cannot split on them and PF20 should pick what P20 picks. The pair therefore measures the fundamentals' contribution in 2010–2015 only, and the hypothesis says so before the run. The coverage gate is method-wide (`runner.preflight_data` refuses if any candidate is fundamentals-aware), so the whole run is recorded under the acknowledgement. The flag is not a silencer: the coverage table is printed either way. |
| Hyperparameters | **base** = Strategy B's pre-registered `TREE_PARAMS` (`strategies/b_model.py`, fixed 2026-10-03 for a different book and never searched): learning rate 0.05, 300 iterations, 15 leaves, 200 per leaf, L2 1.0. **Regularised** = 0.05 / 100 / 7 / 1000 / L2 10. Seed 0, untouched. | Neither was chosen by looking at this data. These six are the only settings ever tried, and there is no off-book tuning run on the dev window. Phase 6 measured that `seed` is inert below 200,000 training rows (the dev store reaches about 57,000), so a seed variant would buy nothing. |
| Trend gate | **one** variant (P20-GATE) behind the lab's standard SPY 200-day switch (`m0007.N20`'s `("SPY", 200)` via `f_factor.trend_on`), which is all cash when SPY closes at or below its 200-day average on d | The handover's caveat is that the binding constraint is the 2008 fall ≤ 20%, and an always-invested 20-name book fell 50%+ in 2008 in every lab precedent (M0024 61%). Without one gated variant the method would be pre-doomed on design §1 by construction. The gate is the lab's standing constant, not a new knob. |
| Rules | `MONTHLY_HOLD_FRAC_GOTRADE_TBAND` (phase 3, id `monthly-hold-frac-gotrade-tband`): monthly, fractional, Gotrade fees, resize band 20% of the holding's own target, **no** cash yield | No owner input, so it stays gate-eligible (plan Decisions). |
| Promotion | **never in this phase**, even when `lab run` prints ELIGIBLE | Plan index: no `lab promote`, no `lab test`. The explore skill's promotion step is overridden here. An eligible result is reported, with `lab walkforward`'s fold record and the kin reading. |
| Where the pre-registration commit lands | committed on `feature/measure-then-learn`, then `git push origin HEAD:main` after a rebase onto `origin/main`. This is the same as phase 5 Step 6 and lands phase 6's allocator on `main` with it. | `lab stage` commits `lab/lab.sqlite` in the main checkout. `main`'s `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` fails ("ran but its method file is gone") unless the method file is on `main` first. |

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `engine/src/seer_engine/lab/methods/m${DIGITS}_tree_ranker.py`. The id is reserved at run time with `lab idea`, after phase 5's method **and** phase 5's queued idea row. Placeholder `MNNNN` / `mNNNN`. The file contains:
  - `METHOD` (id `MNNNN`, family `stock-ml-ranker`, `source_kind="paper"`, `parent_id=None`, 6 candidates: `MNNNN-P20`, `-P50`, `-P50-REG`, `-P20-GATE`, `-PF20`, `-DV20`)
  - allocators `TREE_BOOK` (id `"MNNNN"`, wraps `tree_rank.TREE_RANK`), `TREE_BOOK_FUND` (id `"MNNNN-F"`, wraps `tree_rank.TREE_RANK_FUND`) and `DV_BOOK` (id `"MNNNN-DV"`, the control)
  - classes `TreeBook`, `TreeBookPrepared`, `DollarVolumeBook`, `ControlPrepared`, `BookParams`, `ControlParams`
  - function `model_ready`, constants `BENCH`, `GATE`, `BASE`, `REG`, `ADDED`
- Lab rows in the shared DB (`/home/miftah/seer/lab/lab.sqlite`):
  - one method row (an `idea` row first, overwritten by the run) with six dev trials, plus funding, moments and provenance
  - one survivorship observation
  - one analysis note with its verdict
  - at least one insight
  - one queued `idea` row, which consumes the id after `MNNNN`
  - the file's seen keys
- Commits:
  - the pre-registration `lab: MNNNN pre-registered — …` (method file only) on the feature branch, pushed to `main`
  - a `lab stage` commit in the main checkout, `lab: MNNNN rejected (…)` or `lab: MNNNN dev-eligible — …`

**Signature changes:** none.

**Requires (from earlier phases):**
- Phase 3: `seer_engine.sim.rules.MONTHLY_HOLD_FRAC_GOTRADE_TBAND` exists. Its id is `monthly-hold-frac-gotrade-tband`, with `resize_basis="target"`, `cash_yield=None`, `cost_model="gotrade"`, `fractional=True`, and `rule_owner_inputs(...) == ()`.
- Phase 4: `lab survivorship` defaults `--sv-store` to `$SEER_SV_STORE`, and `/home/miftah/seer/engine/.research-sv` has been rebuilt against the current dev store.
- Phase 5: its method is run, staged and committed on `main`, and its queued idea row exists, so `lab next-id` / `lab idea` here yields the id after both. `main` already carries phases 1–5.
- Phase 6: `seer_engine.lab.tree_rank` exports `TREE_RANK` (id `"TREE"`, `market_fields=("dividends",)`), `TREE_RANK_FUND` (id `"TREEF"`, `market_fields=("dividends","fundamentals")`), `TreeRankAllocator`, `TreeRankParams(top_n, feature_set, learning_rate, max_iter, max_leaf_nodes, min_samples_leaf, l2, train_start, min_train_months, horizon, seed)`, `SCREEN`, `FEATURE_LOOKBACK` (401), `month_ends(start, end)`, `label_end(t, horizon)` and `anchor_for(d)`. It also exports `TreeRankPrepared` with `.inputs` and `.model_on(d, params)`. The history-only path targets nothing (`prepare(history)` gives `inputs is None`).

**Leaves alone (owned by others):** `lab/tree_rank.py` and its tests (phase 6); `sim/*` and presets (phases 1–3); `commands/lab.py` and `--sv-store` (phase 4); phase 5's method file and rows; every existing method file and lab row; `docs/lab/prereg/`; the test-window store.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m${DIGITS}_tree_ranker.py:1` | create | the whole method file (Step 3) |
| `/home/miftah/seer/lab/lab.sqlite` | append (via `lab idea` / `run` / `survivorship` / `note` / `insight` / `stage`) | one method, six dev trials, journal rows |
| `/home/miftah/seer/web/data/lab.json` | regenerate (via `lab stage`) | snapshot of the DB |

## Implementation Steps

All commands use these variables. Export them in **every** shell. A forgotten export silently
writes to the worktree's copy of the DB.

```bash
WT=/home/miftah/.worktrees/seer/measure-then-learn
MAIN=/home/miftah/seer
export SEER_LAB_DB=$MAIN/lab/lab.sqlite
export SEER_RESEARCH_STORE=$MAIN/engine/.research
export SEER_SV_STORE=$MAIN/engine/.research-sv
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PY=$WT/engine/.venv/bin/python
LAB="$PY -m seer_engine lab"
SCRATCH=/tmp/claude-1000/phase7-tree-ranker && mkdir -p $SCRATCH
```

### Step 1: Preflight. Prerequisites landed, the tools point at this tree, nothing half-done

**File:** none (read-only checks)
**Change:**
1. If `$WT/engine/.venv` is missing, create it: `python3.11 -m venv $WT/engine/.venv && $WT/engine/.venv/bin/pip install -e "$WT/engine[dev]"`.
2. `$PY -c "import seer_engine; print(seer_engine.__file__)"` must print a path under `$WT/engine/src`.
3. Bring the worktree level with `main`, which by now carries phase 5's staging commit:
   `git -C $WT fetch origin && git -C $WT rebase origin/main`. If the rebase conflicts, stop and report.
4. Run the check script below with `$PY -`. Every line must print `ok`. If one does not, stop: a prerequisite phase is missing.
5. `git -C $MAIN status --porcelain -- lab/lab.sqlite web/data/lab.json`. If it is non-empty, another session has unpublished rows. Do not touch them. They are published with this phase's rows in Step 12.
6. `$LAB status`. Write N, the luck bar (`DSR >= 0.90`) and the test looks into `$SCRATCH/analysis.md`. They are for the note, and never typed into insight text as ids.
7. (Already measured 2026-10-12. Re-run only if the store's manifest fingerprint is no longer `8817191c23ef…`.) Panel coverage, read only:
   ```bash
   $PY - <<'EOF'
   import os
   from pathlib import Path
   from seer_engine import research
   from seer_engine.fundamentals import coverage
   data = research.load_store(Path(os.environ["SEER_RESEARCH_STORE"]))
   cov = coverage.measure(data.market.fundamentals)
   print(data.fingerprint[:12], round(cov.fraction, 4))
   EOF
   ```
   Expected `0.3151`. If the store changed and the fraction is below 0.31, use the printed fraction rounded **down** to two decimals as `F` in Step 7 and in the hypothesis sentence that names it (Step 3, before the commit).

**Code** (Step 1.4):
```python
from seer_engine.lab import tree_rank as T
from seer_engine.sim import rules as R

r = R.MONTHLY_HOLD_FRAC_GOTRADE_TBAND
ok = (r.id == "monthly-hold-frac-gotrade-tband" and r.engine == "book" and r.cadence == "monthly"
      and r.fractional and r.cost_model == "gotrade" and r.resize and r.resize_basis == "target"
      and r.cash_yield is None and r.idle_symbol is None and R.rule_owner_inputs(r) == ())
print("ok" if ok else f"WRONG preset: {r}")
print("ok" if r in R.PRESETS else "preset not in PRESETS")
print("ok" if (T.TREE_RANK.id, T.TREE_RANK_FUND.id) == ("TREE", "TREEF") else "allocator ids differ")
print("ok" if T.TREE_RANK.market_fields == ("dividends",) else f"TREE fields {T.TREE_RANK.market_fields}")
print("ok" if "fundamentals" in T.TREE_RANK_FUND.market_fields else "TREEF does not read fundamentals")
p = T.TreeRankParams()
print("ok" if (p.top_n, p.feature_set, p.learning_rate, p.max_iter, p.max_leaf_nodes, p.min_samples_leaf,
               p.l2, p.train_start.isoformat(), p.min_train_months, p.horizon, p.seed)
      == (20, "price", 0.05, 300, 15, 200, 1.0, "1996-01-31", 35, 21, 0) else f"defaults moved: {p}")
print("ok" if T.FEATURE_LOOKBACK <= 473 else f"lookback {T.FEATURE_LOOKBACK} breaks the smoke market")
```
**Impact:** none. Reads only.

### Step 2: Check the idea is new, then reserve the id

**File:** shared DB (one `idea` row)
**Change:**
1. `$LAB seen --find tree`, `$LAB seen --find gradient`, `$LAB seen --find "machine"` and `$LAB seen --find ranker`.
   - Known on 2026-10-12: `H-B`, "Strategy B (gradient-boosted ranker on A's bracket)", family `ml-ranker`, `rejected`. It was a daily bracket ranker on design v0, one round, a closed record. This method is a monthly long-only book with walk-forward refits, so it is not a duplicate, and the hypothesis names H-B.
   - If a later session has already registered a monthly tree or ML ranker on the member book, stop and report it. Never duplicate.
2. Reserve the id atomically (a `lab next-id` alone can race a Sera session):
   ```bash
   MID=$($LAB idea \
     --name "A learned stock ranker: gradient-boosted trees combine the lab's own signals, refitted once a year" \
     --family stock-ml-ranker \
     --source-kind paper \
     --source-ref "Gu, Kelly & Xiu (2020), Empirical Asset Pricing via Machine Learning, Review of Financial Studies 33(5)" \
     --hypothesis "Gradient-boosted trees, refitted every year on only what was known then, rank index members on the lab's existing signals; the top 20 or 50 equal-weight monthly at Gotrade's fees, beside a same-shape book picked by trading volume to measure what the model adds.")
   echo "$MID"                         # e.g. M0130
   DIGITS=$(echo "$MID" | tr -d 'M')   # e.g. 0130
   ```
   - If `lab idea` prints more than the id, take the `M\d{4}` token: `MID=$(… | grep -oE 'M[0-9]{4}' | head -1)`.
   - Exit 2: read the message and act on it. Never retry blindly.

**Impact:** one `idea` row. `main`'s `test_lab_snapshot.py` stays red until Step 12 stages it. That is expected and documented in the explore skill.

### Step 3: Write the method file

**File:** `$WT/engine/src/seer_engine/lab/methods/m${DIGITS}_tree_ranker.py` (new)
**Change:** write the file below verbatim, then fill the id. Set `ADDED` to the run date if it is not 2026-10-12.
```bash
F=$WT/engine/src/seer_engine/lab/methods/m${DIGITS}_tree_ranker.py
# (write the code block below to $F)
sed -i "s/MNNNN/$MID/g" "$F"
grep -c MNNNN "$F"     # must print 0
```
**Code:**
```python
"""MNNNN — A learned stock ranker: gradient-boosted trees combine the lab's own signals.

Source: Gu, Kelly & Xiu (2020), "Empirical Asset Pricing via Machine Learning", Review of
Financial Studies 33(5). Handover 2026-10-12 ("measure then learn"), Step 1, item 5.

Idea: every method in the lab so far ranks on ONE hand-chosen signal. This one lets a
gradient-boosted tree learn, walk-forward and point in time, how to combine signals the lab
already computes: 12-1 momentum, volatility, dollar volume, M0007's residual momentum, the
52-week-high distance, M0070's dividend-raise event, the trailing dividend yield and, in one
variant, the four SEC EDGAR factors. Gu, Kelly & Xiu found trees beat linear ranking, but mostly
in small caps and long-short before costs. This is the large-cap, long-only, real-fee test of
whether any of that survives.

THE MODEL is phase 6's ``lab.tree_rank`` allocator, unchanged: ``HistGradientBoostingRegressor``
refitted once a year (at each year's last session) on every month-end sample since 1996-01-31
whose forward 21-session return rank was already known, with features rank-normalised per date.
It holds the top N predictions at equal weight. Nothing dated after the decision date is read.

THE WRAPPER (``TreeBook``) adds two pre-registered rules around it and nothing else:

    * **Before the first model, hold SPY.** The first refit with enough history (35 labelled
      month-ends) is 1998-12-31, and a member book's dev window opens in early 1996. Three years
      of cash during SPY's 1996-98 run would decide "beats SPY" by a data-availability artefact.
      Holding the yardstick while there is nothing to learn from is neutral against it, and is
      identical in every variant, so each paired difference is the model alone. "Is there a
      model on d" is the calendar rule ``model_ready``, shared with the control, so both kinds of
      variant switch on the same session.
    * **An optional SPY 200-day switch** (``gate``), the lab's standing constant
      (``m0007.N20``'s trend), for the one variant that asks whether the model plus the lab's
      usual safety rule can keep the 2008 fall inside 20%.

THE CONTROL (``DollarVolumeBook``) is the same book without the model: the 20 screen-eligible
members (the tree's own screen, ``tree_rank.SCREEN``) with the largest 20-day dollar volume,
equal weight, on the same 401-bar lookback, the same SPY-before-the-model rule and the same
rules. It ranks on size of trading, which forecasts nothing, so tree minus control is what the
model's picking adds over the shape of the book. It is deliberately NOT a momentum book: the hard
gate's behavioural kin test (``lab/hardgate.py`` D14) reads every dev variant of a method, and one
momentum variant correlating with the test-failed momentum books would make every tree variant
here unpromotable.

THE SIX VARIANTS are the only hyperparameter settings this lab ever tries for this idea. Every
one of them counts, and none was chosen by looking at dev results. The base tree is Strategy B's
pre-registered ``TREE_PARAMS`` (``strategies/b_model.py``, fixed 2026-10-03 for a different book).
The regularised tree is a fixed alternative with fewer, shallower, fatter-leaved trees.

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
from seer_engine.lab.tree_rank import (
    FEATURE_LOOKBACK,
    SCREEN,
    TREE_RANK,
    TREE_RANK_FUND,
    TreeRankAllocator,
    TreeRankParams,
    anchor_for,
    label_end,
    month_ends,
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

ADDED = date(2026, 10, 12)
BENCH = "SPY"  # held before the first model, and the gate's instrument
GATE = N20  # the lab's standing SPY 200-day switch (F4-MOM12-N20-TREND's), read only for its trend
BASE = TreeRankParams()  # Strategy B's pre-registered tree: lr 0.05, 300 iters, 15 leaves, 200/leaf, L2 1
REG = TreeRankParams(
    top_n=50, learning_rate=0.05, max_iter=100, max_leaf_nodes=7, min_samples_leaf=1000, l2=10.0
)


def model_ready(data_date: date, train_start: date, min_train_months: int, horizon: int) -> bool:
    """Is there a model to decide on ``data_date``? The calendar half of ``tree_rank``'s rule.

    The model deciding on d is the one refitted at ``anchor_for(d)``. It exists when at least
    ``min_train_months`` month-ends from ``train_start`` on had their label read by the anchor.
    Calendar only, so the control (which has no model) switches on the same session as the trees.
    """
    anchor = anchor_for(data_date)
    if anchor < train_start:
        return False
    ends = month_ends(train_start, anchor)
    if len(ends) < min_train_months:
        return False
    labelled = sum(1 for t in ends if label_end(t, horizon) <= anchor)
    return labelled >= min_train_months


def _bench(history: Mapping[str, History], data_date: date) -> tuple[Target, ...]:
    """SPY at full weight, priced at d's close; nothing when SPY has no bar dated d."""
    h = history.get(BENCH)
    if h is None or h.index_of(data_date) is None:
        return ()
    t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
    return () if t is None else (t,)


# --------------------------------------------------------------------------- the tree book


@dataclass(frozen=True, slots=True)
class BookParams:
    """The tree's own params, and whether the SPY 200-day switch stands in front of it."""

    tree: TreeRankParams
    gate: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.tree, TreeRankParams):
            raise TypeError(f"tree must be TreeRankParams, got {type(self.tree).__name__}")
        if not isinstance(self.gate, bool):
            raise TypeError(f"gate must be a bool, got {type(self.gate).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = dict(self.tree.as_dict())
        out["gate"] = "SPY:200" if self.gate else "none"
        return out


@dataclass(frozen=True, slots=True, eq=False)
class TreeBookPrepared:
    """The inner tree's prepared value, and the bars the SPY fill and the gate read.

    ``history`` is None on the history-only path, which by the market-aware contract targets
    nothing (tests/test_lab_methods.py).
    """

    inner: Any
    history: Mapping[str, History] | None


class TreeBook:
    """Phase 6's tree ranker, SPY before its first model, optionally behind the SPY 200-day switch."""

    def __init__(self, inner: TreeRankAllocator, ident: str) -> None:
        self.inner = inner
        self.id = ident
        # What `lab run` gates on (runner.market_fields): exactly the inner tree's fields.
        self.market_fields: tuple[str, ...] = tuple(inner.market_fields)

    def _check(self, params: object) -> BookParams:
        if not isinstance(params, BookParams):
            raise TypeError(f"params must be BookParams, got {type(params).__name__}")
        return params

    def lookback(self, params: Any) -> int:
        p = self._check(params)
        n = self.inner.lookback(p.tree)
        return max(n, factor_lookback(GATE)) if p.gate else n

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = self._check(params)
        return tuple(sorted({BENCH, *self.inner.symbols(p.tree)}))

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

    def prepare(self, history: Mapping[str, History]) -> TreeBookPrepared:
        return TreeBookPrepared(self.inner.prepare(history), None)

    def prepare_market(self, market: Any) -> TreeBookPrepared:
        return TreeBookPrepared(self.inner.prepare_market(market), MappingProxyType(dict(market.history)))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = self._check(params)
        if not isinstance(prepared, TreeBookPrepared):
            raise TypeError(f"prepared must be TreeBookPrepared, got {type(prepared).__name__}")
        if prepared.history is None:
            return ()
        if p.gate and not trend_on(prepared.history, data_date, GATE):
            return ()
        if not model_ready(data_date, p.tree.train_start, p.tree.min_train_months, p.tree.horizon):
            return _bench(prepared.history, data_date)
        return self.inner.targets_prepared(prepared.inner, members, data_date, held, p.tree)


TREE_BOOK = TreeBook(TREE_RANK, "MNNNN")
TREE_BOOK_FUND = TreeBook(TREE_RANK_FUND, "MNNNN-F")


# --------------------------------------------------------------------------- the control


@dataclass(frozen=True, slots=True)
class ControlParams:
    """The control's book size, and the tree clock it shares (defaults: the tree's own)."""

    top_n: int = BASE.top_n
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
        if not isinstance(self.train_start, date):
            raise TypeError(f"train_start must be a date, got {type(self.train_start).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {
            "top_n": str(self.top_n),
            "train_start": self.train_start.isoformat(),
            "min_train_months": str(self.min_train_months),
            "horizon": str(self.horizon),
        }


@dataclass(frozen=True, slots=True, eq=False)
class ControlPrepared:
    history: Mapping[str, History]
    factor: FactorPrepared


class DollarVolumeBook:
    """The tree book's shape without the model: the most-traded eligible members, equal weight."""

    id = "MNNNN-DV"

    def _check(self, params: object) -> ControlParams:
        if not isinstance(params, ControlParams):
            raise TypeError(f"params must be ControlParams, got {type(params).__name__}")
        return params

    def lookback(self, params: Any) -> int:
        self._check(params)
        return FEATURE_LOOKBACK  # the trees' window, so all six variants score the same sessions

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
        if not model_ready(data_date, p.train_start, p.min_train_months, p.horizon):
            return _bench(prepared.history, data_date)
        return self._pick(prepared.factor.rows_on(members, data_date, SCREEN), p)


DV_BOOK = DollarVolumeBook()


# --------------------------------------------------------------------------- the method


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"MNNNN-{suffix}", family="MNNNN", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="MNNNN",
    name="A learned stock ranker: gradient-boosted trees combine the lab's own signals, refitted once a year",
    family="stock-ml-ranker",
    source_kind="paper",
    source_ref=(
        "Gu, Kelly & Xiu (2020), Empirical Asset Pricing via Machine Learning, Review of Financial "
        "Studies 33(5); handover 2026-10-12 (measure then learn), Step 1 item 5"
    ),
    parent_id=None,
    hypothesis=(
        "Every method in this lab ranks on one hand-chosen signal, and the closest near misses all "
        "lean on the same one, residual momentum. Gu, Kelly & Xiu (2020) found that regression trees "
        "combining many such signals rank US stocks better than any linear combination. This method "
        "asks whether a small part of that survives where this lab has to live: large-cap index "
        "members, long only, monthly, Gotrade's real fees, fractional shares, the owner's 5,000,000 "
        "IDR monthly deposits, and a resize band measured against each holding's own target. THE "
        "MODEL: scikit-learn's histogram gradient-boosted trees, refitted once a year at the last "
        "session of each year on every month-end sample since January 1996 whose next-21-session "
        "return rank was already known by then (an expanding window, nothing read after the "
        "decision date). Seven features the lab already computes, each rank-normalised per date: "
        "12-1 momentum, 60-day volatility, 20-day dollar volume, M0007-N20-RAW's residual momentum, "
        "distance from the 52-week high, M0070's dividend-raise event and the trailing dividend "
        "yield; the PF20 variant adds the four SEC EDGAR factors (value, quality, profitability, "
        "earnings surprise). The book holds the top N predictions at equal weight. The first "
        "refit with enough history (35 labelled month-ends) is 1998-12-31; until then every "
        "variant, the control included, holds SPY, so 1996-1998 is the same in all six and every "
        "paired difference below is the model alone. SIX VARIANTS, THE ONLY SETTINGS EVER TRIED: no "
        "hyperparameter was tuned on the dev window off the books, and none will be; a change after "
        "a result is a new method. The base tree is Strategy B's pre-registered setting (learning "
        "rate 0.05, 300 trees, 15 leaves, at least 200 samples per leaf, L2 1.0), fixed on "
        "2026-10-03 for a different book and never searched; the regularised tree (100 trees, 7 "
        "leaves, 1,000 per leaf, L2 10) is the one fixed alternative. The seed is 0 and is inert at "
        "this sample size. P20 and P50 hold the top 20 and top 50; P50-REG is the regularised tree "
        "at 50; P20-GATE is P20 behind the lab's standing SPY 200-day switch; PF20 is P20 with the "
        "fundamentals; DV20 is the CONTROL, the same 20-name equal-weight book on the same screen, "
        "window and SPY-before-the-model rule, picked by 20-day dollar volume, which forecasts "
        "nothing. The control is deliberately not a momentum book: the hard gate reads every "
        "variant's behaviour, and one momentum variant moving with the four test-failed momentum "
        "books would bar every tree variant from promotion. The comparison with momentum is made in "
        "the analysis against the lab's recorded real-fee momentum books instead. FUNDAMENTALS: the "
        "store's EDGAR panel can rank 20 names on only 31.5% of the dev window (none of 1996-2008, "
        "5 of 12 months of 2009, all of 2010-2015), so the run is recorded under --allow-coverage "
        "0.31, knowingly; before 2009 the four columns are empty and PF20 should pick what P20 "
        "picks, so PF20 minus P20 measures the fundamentals in 2010-2015 only. WHAT COUNTS AS THE "
        "MODEL ADDING SOMETHING, fixed now: P20 beats DV20 by at least 2 points a year of funded "
        "return over 1999-2015 AND is ahead of it in 2009-2015, the era most like today. WHAT COUNTS "
        "AS A METHOD: a variant clears every design section 1 bar at DSR >= 0.90 at the lab's N, "
        "including the worst fall <= 20%, which only P20-GATE is built to have a chance at. No "
        "variant is promoted in this run, whatever it shows: the test window is not touched."
    ),
    expected_failure=(
        "Most likely the model adds nothing measurable over the dollar-volume control after fees. "
        "Gu, Kelly & Xiu's edge is concentrated in small and illiquid stocks and in the short leg, "
        "and is measured before costs; this universe is the S&P 500 union the Nasdaq-100 above $20M "
        "a day, long only, and a 20-to-50-name book re-picked monthly pays Gotrade's minimum fees on "
        "$29-70 slots. The paper was published in 2020 but its inputs (momentum and its cousins) "
        "were published long before the dev window ended, so any dev edge is the pre-crowd edge and "
        "likely to fade. Second, the trees will probably learn mostly momentum: residual momentum "
        "and 12-1 momentum are the strongest inputs, so the picks may move with the lab's "
        "test-failed momentum books closely enough that the hard gate reads them as kin, which would "
        "be the right verdict on a model that only re-discovered momentum. Third, every ungated "
        "variant will fall far more than 20% in 2008 -- a fully invested 20-name book fell 50-60% in "
        "every lab precedent -- and the monthly-read SPY switch in P20-GATE reacted late in 2008 "
        "for every lab book that used it, so even the gated variant is likely to miss the 20% bar, "
        "as M0007-N20-RAW did once the missing dead companies were added back (19.6% on the dev "
        "store, 23.5% on the survivorship-check store). Fourth, the training set inherits the "
        "store's survivorship: about half of all index members ever listed are missing, mostly the "
        "ones that died, so the model learns from winners' histories and the survivorship check is "
        "expected to cost it more than the 1-1.4 points a year it cost the hand-built momentum "
        "books. Fifth, PF20 is expected to differ from P20 by noise: the fundamentals enter "
        "training only from late 2009 and are a small slice of every refit's history even by 2014. "
        "Sixth, the regularised tree is expected to sit between the base tree and the control, and "
        "P50 to trail P20 on fees. Finally, twenty years of monthly cross-sections is a small "
        "sample for a learner: about 57,000 training rows by 2014, heavily correlated within each "
        "month, so a DSR at the lab's N may not separate a real ranking skill from luck even if the "
        "returns look good."
    ),
    candidates=(
        _v("P20", TREE_BOOK, BookParams(BASE),
           "The base tree on the seven price and dividend features, top 20, equal weight"),
        _v("P50", TREE_BOOK, BookParams(TreeRankParams(top_n=50)),
           "The same base tree holding its top 50"),
        _v("P50-REG", TREE_BOOK, BookParams(REG),
           "A more regularised tree (100 trees, 7 leaves, 1000 per leaf, L2 10), top 50"),
        _v("P20-GATE", TREE_BOOK, BookParams(BASE, gate=True),
           "The base tree's top 20 behind the lab's standing SPY 200-day switch"),
        _v("PF20", TREE_BOOK_FUND, BookParams(TreeRankParams(feature_set="price+fund")),
           "The base tree's top 20 with the four SEC fundamentals added (they exist from 2009 only)"),
        _v("DV20", DV_BOOK, ControlParams(),
           "Control: the same 20-name book picked by trading volume, no model"),
    ),
    seen_keys=(
        "concept:gradient-boosted-tree-ranker",
        "concept:ml-cross-sectional-ranker",
        "concept:walk-forward-annual-refit",
        "concept:learned-signal-combination",
    ),
)
```
**Impact:** a new method module. `discover()` picks it up. `test_lab_methods.py` runs its purity, smoke-window, allocator-contract and id-uniqueness checks automatically. Three new allocator ids: `MNNNN`, `MNNNN-F`, `MNNNN-DV`.

### Step 4: Check the shared clock against the real model, before anything is committed

**File:** none (read only, nothing recorded)
**Change:** the control and the trees must switch from SPY to their own picks on the same
session. This check reads the dev store and fits phase 6's yearly models (about 10 s). It reads
**only whether a model exists**, never a return, a pick or a score, so it does not spend or inform anything.
```bash
cd $WT && $PY - <<EOF
import os
from datetime import date
from pathlib import Path
from seer_engine import research
from seer_engine.lab.tree_rank import TREE_RANK, TreeRankParams, month_ends
from seer_engine.lab.methods.m${DIGITS}_tree_ranker import model_ready
data = research.load_store(Path(os.environ["SEER_RESEARCH_STORE"]))
prep = TREE_RANK.prepare_market(data.market)
p = TreeRankParams()
bad = [d for d in month_ends(date(1996, 1, 31), date(2015, 9, 30))
       if (prep.model_on(d, p) is not None) != model_ready(d, p.train_start, p.min_train_months, p.horizon)]
first = next(d for d in month_ends(date(1996, 1, 31), date(2015, 9, 30)) if model_ready(d, p.train_start, p.min_train_months, p.horizon))
print("disagreements:", bad[:5], len(bad), "first model month-end:", first)
EOF
```
Expected: `disagreements: [] 0 first model month-end: 1998-12-31`. If they disagree, stop. Do not
commit, and report it to phase 6's owner. The rule in the file must equal the allocator's before the
pre-registration freezes it. A change to `model_ready` here is still before the commit, so it is allowed.

**Impact:** none.

### Step 5: Contract tests, then the pre-registration commit

**File:** `$F` (commit)
**Change:**
1. `cd $WT/engine && $PY -m pytest -q tests/test_lab_methods.py -k "$MID or unique or pure" && $WT/engine/.venv/bin/ruff check src tests`. Then run the full contract file `$PY -m pytest -q tests/test_lab_methods.py`. If a contract check fails, fix the method file, never the test.
2. Full suite with `PG_TEST_URL` set: `cd $WT/engine && $PY -m pytest -q tests`. `test_lab_snapshot.py` reads the worktree's committed DB, not the shared one, so it stays green here.
3. Commit the method file alone:
   ```bash
   git -C $WT add -- engine/src/seer_engine/lab/methods/m${DIGITS}_tree_ranker.py
   git -C $WT commit -F - <<EOF
   lab: $MID pre-registered — a learned stock ranker, gradient-boosted trees refitted yearly

   Six fixed variants on the target-band real-fee tape, the only settings ever tried:
   base tree top 20 and top 50, a regularised tree at 50, top 20 behind the SPY
   200-day switch, top 20 with the SEC fundamentals (run under --allow-coverage 0.31:
   the panel covers 31.5% of the dev window, none before 2009), and a same-shape
   control picked by trading volume. Every variant holds SPY until the first yearly
   model (1998-12-31). Assumed: Strategy B's pre-registered tree settings as the base;
   no momentum control, because one momentum variant would make the whole method kin
   of the test-failed momentum books.

   Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
   EOF
   ```
**Impact:** the hypothesis is frozen at this commit. From here on the file is never edited.

### Step 6: Land the branch on `main` before the run

**File:** none (git only)
**Change:** the same as phase 5 Step 6:
```bash
git -C $WT fetch origin
git -C $WT rebase origin/main
cd $WT/engine && $PY -m pytest -q tests              # re-verify after the rebase
git -C $WT push origin HEAD:main
git -C $WT push origin HEAD:feature/measure-then-learn --force-with-lease
```
- A rebase that conflicts in `lab/lab.sqlite` or `web/data/lab.json`: stop, because something else is wrong.
- Landing on `main` mid-set is decided (plan index Decisions); do not pause for a merge.
- `git -C $WT status --porcelain -- engine/src/seer_engine/lab/methods/` must be empty, because `lab run` checks it.

**Impact:** `main` gains phase 6's allocator and this method file. A later `lab stage` cannot red `main` with "ran but its method file is gone".

### Step 7: Run it on the dev window (background-safe)

**File:** shared DB
**Change:**
```bash
cd $WT && ( $LAB run $MID --store $SEER_RESEARCH_STORE --allow-coverage 0.31 > $SCRATCH/run.log 2>&1; echo "EXIT=$?" >> $SCRATCH/run.log )
```
Run it with the Bash tool's `run_in_background: true`, or under `nohup … &` from a plain shell.
Then wait for `EXIT=` with a Monitor until-loop, for example
`until grep -q '^EXIT=' $SCRATCH/run.log; do sleep 10; done; tail -40 $SCRATCH/run.log`.
Do not poll in a foreground loop.

- **Run time estimate.** Store load about 15–20 s. Phase 6 measured `prepare_market` at 0.2 s and every yearly fit for 1996–2015 at about 9 s on one thread. Fits are shared between variants with the same allocator id and tree settings (P20, P50 and P20-GATE share one set), so there are four sets: base, regularised, fundamentals and none for the control. The six book simulations over about 5,000 sessions with member books dominate, at about 1–3 min each. **Expect 10–25 minutes in total.** Treat 90 minutes with no `EXIT=` as a hang: read `run.log`, `ps` the process and report it. Never start a second `lab run` of the same method while one is alive.
- It prints the coverage table first (0.3151 against the acknowledged 0.31), then one line per variant.
- **Exit 2** means the lab refused. Read the message:
  - coverage below 0.31 (the store changed): no trial was written. Re-run with the printed fraction rounded down, and say so in the note.
  - "Commit the method file first": Step 5/6 was not clean. Fix the git state, never the flag.
  - a D10 price-pin refusal: the wrong store. `SEER_RESEARCH_STORE` must be `$MAIN/engine/.research`.
  - "already ran" / "repeats": stop and report. Never rename to dodge it.
- **Exit 1** is an error. `$LAB show $MID`: if **no** trial was written, fix the cause (an environment or tooling problem, never the method file) and run again. If any trial was written, stop and report. A partial record is explained in the note, never redone.
- After it finishes, `$LAB show $MID > $SCRATCH/show.txt`. All six variants must be present, each with a `funded:` line.

**Impact:**
- Six dev trials.
- Method status becomes `rejected`, or `dev-eligible`.
- N rises by one for the whole lab, because variants add to `var_trials`, not N.

### Step 8: The reports that spend nothing

**File:** shared DB (one observation)
**Change:**
```bash
cd $WT && $LAB survivorship $MID --csv $SCRATCH/sv.csv > $SCRATCH/sv.txt 2>&1; echo "EXIT=$?" >> $SCRATCH/sv.txt   # background; about 2x the run time
cd $WT && $LAB walkforward $MID > $SCRATCH/wf.txt 2>&1                                                      # no store, seconds
```
- `lab survivorship` re-runs every recorded variant on the dev store and on `$SEER_SV_STORE`. It journals one plain-words observation. Read the dev column's "reproduced" first: a variant that does not reproduce makes its side-by-side meaningless, and the note must say which. It has no coverage gate, and the sv store carries `fundamentals.csv`, so PF20 runs there too.
- If `lab survivorship` exits 2 because the sv store's manifest does not name the current dev store, the check store is stale. The check is never skipped (plan index Decisions, "A stale survivorship-check store at run time"): rebuild it offline with phase 4's runbook command, then run the check again:
  ```bash
  $PY -m seer_engine survivorship_store --build --out $MAIN/engine/.research-sv \
      --source $MAIN/engine/.research --cache $MAIN/engine/.cache/eodhd
  ```
  A second refusal after a successful rebuild is a phase 4 defect: stop and report it.
- `lab walkforward` gives the fold record (how many walk-forward folds each variant beat SPY in). It writes nothing.
- No `lab promote` and no `lab test`, even on ELIGIBLE (plan index, invariant 5).

**Impact:** one observation row. N and looks do not change.

### Step 9: Analyse honestly and write the note

**File:** shared DB (`lab note`)
**Change:** write `$SCRATCH/analysis.md` (scratch, not committed). It is the audit record, so ids and numbers are allowed there, but plain sentences. It must cover, in this order:
1. **Result against total-return SPY** for each variant: funded CAGR, the worst fall measured on the book without its deposits, profit factor, trades, DSR at N. State the N and the bar (`DSR >= 0.90`) exactly as `lab status` prints them. List every failed condition with its margin.
2. **Did the model add anything?** P20 against DV20 over 1999–2015 and over 2009–2015, against the pre-registered bar (≥ 2 points a year, and ahead in 2009–2015). Say plainly whether it held.
3. **Breadth and regularisation:** P50 against P20 (fees on $29 slots), and P50-REG against P50.
4. **The fundamentals:** PF20 against P20. Before 2010 they should be identical or nearly so. Say whether they were, and what 2010–2015 alone shows. State that the run was recorded under the 0.31 coverage acknowledgement and what that means.
5. **The gate and 2008:** P20-GATE against P20. When the worst fall hit and how deep, and whether the switch reacted in time.
6. **1996–1998:** confirm that all six held SPY, and that those years add nothing to any paired difference.
7. **Survivorship:** how much each variant lost on the check store, against the 1–1.4 points a year the momentum books lost.
8. **Kin and folds:** what `lab walkforward` printed. If anything is dev-eligible, also whether the picks move with the test-failed momentum books. `lab status` lists the hard gate's refusals.
9. **Comparison with momentum:** the lab's recorded real-fee residual-momentum books (`lab show M0032`, or `lab costs M0007` for the 0.1%-era near miss). Compare real fees with real fees only.
10. **Why:** the mechanism. Which features did the trees lean on, if that can be read from the result without a new run? Did the hypothesis hold, and did the expected failure happen?
11. A closing paragraph that starts **`My opinion:`**. Say whether a learned ranker is worth more lab ids here, whether the small neural net (handover item 6) is earned (only if the trees showed something), and what to try next. Commit to a view.

Then:
```bash
cd $WT && $LAB note $MID --file $SCRATCH/analysis.md --verdict "<one plain line, no ids, e.g. The learned ranker picked no better than a book chosen by trading volume, and fell too far in 2008>"
```
**Impact:** analysis and verdict on the method row.

### Step 10: Journal at least one insight

**File:** shared DB
**Change:** at least one `observation`. Add a `risk` or `data-wish` if the run earns one, for example the fundamentals panel starting in 2009. Plain words for a curious non-trader:
- no ids, file paths, column names, digests or backticks
- name methods by what they do ("the learned ranker", "the most-traded control")
- every number carries its meaning
```bash
cd $WT && $LAB insight --kind observation --method $MID \
  --title "<the point in one plain line, e.g. Letting a model combine our signals did not beat simply holding the most-traded big companies>" \
  --body "<what happened, why it matters, what to do about it, in everyday words>"
```
**Impact:** one or more insight rows.

### Step 11: Queue the next idea

**File:** shared DB
**Change:** run `$LAB seen --find <words>` first, then queue one idea drawn from the result:
- If the model beat the control on the pre-registered bar: `--name "A small neural network on the same signals and the same yearly refits" --family stock-ml-ranker --source-kind variation --parent $MID` (handover item 6, earned only now).
- If it did not: `--name "<the plainest lesson, e.g. which single input the trees leaned on, tested on its own behind the switch>" --family <the family of what it ranks on> --source-kind variation --parent $MID`.

This idea row takes the id after `$MID`.

**Impact:** one idea row.

### Step 12: Stage and publish

**File:** `$MAIN/lab/lab.sqlite`, `$MAIN/web/data/lab.json`
**Change:** the same pattern as phase 5 Step 12. Commit by explicit pathspec only:
```bash
cd $WT && $LAB stage
git -C $MAIN commit -F - -- lab/lab.sqlite web/data/lab.json <<EOF
lab: $MID rejected (<plain reason, e.g. the learned ranker picked no better than a book chosen by trading volume>)

Six variants on the target-band real-fee tape: <one line: tree vs control, the gate in 2008, fundamentals>.
Survivorship check: <one line>. N and test looks as lab status printed them.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git -C $MAIN -c rebase.autoStash=true pull --rebase origin main
git -C $MAIN push origin main
cd $MAIN/engine && $MAIN/engine/.venv/bin/python -m pytest -q tests     # main now has phases 1-7; must be green
git -C $WT fetch origin && git -C $WT rebase origin/main && git -C $WT push origin HEAD:feature/measure-then-learn --force-with-lease
```
- If the status is `dev-eligible`, the subject is `lab: $MID dev-eligible — <plain line>`, and the body says "not promoted: this plan set never touches the test window". Promotion is left to a later explore session (see Handoffs).
- Never `git add -A`. Never check out, restore or stash `lab/lab.sqlite` by hand.
- Report: the idea, the result against SPY, the verdict, the insight, the next idea, N and the test looks (unchanged).

**Impact:**
- `main` carries the rows and the snapshot.
- Vercel redeploys `/sera`.
- CI's lab.json/lab.sqlite agreement holds.

## Verification

**Build:** `cd $WT/engine && $PY -c "from seer_engine.lab.method import discover; m,_ = discover()['$MID']; print(m.family, len(m.candidates), sorted({c.allocator.id for c in m.candidates}))"` prints `stock-ml-ranker 6 ['MNNNN', 'MNNNN-DV', 'MNNNN-F']`, with the real id.
**Tests:**
- Before the pre-registration: `cd $WT/engine && $PY -m pytest -q tests/test_lab_methods.py && $WT/engine/.venv/bin/ruff check src tests`, then the full suite with `PG_TEST_URL` set.
- After staging: `cd $MAIN/engine && $MAIN/engine/.venv/bin/python -m pytest -q tests`. This includes `test_lab_snapshot.py`, plus the frozen-sha and digest checks in `test_lab_methods.py`.

**Manual check:**
- `$LAB show $MID` shows six dev trials, each with a `funded:` line.
- `$LAB status` shows N one higher and test looks unchanged.
- The method page on seertrade.site/sera, after Vercel rebuilds, shows the verdict and note in plain words.

**Exit criteria:**
- The method file is on `main` in a commit that contains nothing else and predates every trial.
- Six dev trials are recorded, with a survivorship observation, a note ending in "My opinion:", at least one plain-words insight and one queued idea.
- `lab stage` is committed and pushed, and `main`'s suite is green.
- No test-window trial, no promotion.

## Handoffs

- **Phase 6 (R5), reconciled:** every name this file imports from `seer_engine.lab.tree_rank` (`FEATURE_LOOKBACK`, `SCREEN`, `TREE_RANK`, `TREE_RANK_FUND`, `TreeRankAllocator`, `TreeRankParams`, `anchor_for`, `label_end`, `month_ends`) and every attribute it reads (`TreeRankPrepared.inputs`, `.model_on`, `TreeRankAllocator.market_fields`, `.prepare`, `.prepare_market`, `.targets_prepared`, `.lookback`, `.symbols`) exists in phase 6's module as planned. Phase 6 exports no calendar-only readiness helper: its `TreeRankPrepared.model` counts month-ends with at least one finite label, which reads data, so `model_ready` stays in this file as planned, and Step 4 proves it agrees with `model_on` on the real store before the pre-registration commit.
- **Landing (decided, plan index Decisions):** phase 5 and this phase both push the feature branch to `main` mid-set (phase 5 Step 6, this Step 6). This phase runs only after phase 5 has landed, run, staged and queued its idea, so its `lab idea` id is the one after both.
- **Later explore session (not this plan set):** if a variant ends `dev-eligible`, promotion is a separate, explicit decision. It must first read `lab walkforward` and the hard gate's kin reading. This set never touches the test window.
- **Handover item 6 (small neural net):** queued as an idea in Step 11 only if the trees beat the control on the pre-registered bar. Otherwise it is out of scope.
- **Handover item 7 (daily inference / committed model artifact):** only if a method passes the dev gate. Not in this set.
- **Data wish:** an EDGAR panel before 2009 (or another point-in-time fundamentals source) is what would make the fundamentals variant meaningful across the dev window. Record it as a `data-wish` insight in Step 10 if the run bears it out.

## Rollback

- **Before Step 7:** revert the pre-registration commit on the branch, and on `main` if it was pushed. Then `$LAB drop $MID --why "<reason>"` for the reserved idea row. Nothing was measured.
- **After Step 7:** the rows are append-only by design and cannot be undone. A mistaken run is explained in the note, and a follow-up is a new variation method. The method file must stay on `main` forever, because `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` requires it.
- **Staging commit:** revert it on `main` only together with the DB rows it carries, which is never done. Leave it in place and explain any problem in a note.

> Adopted from `/home/miftah/seer/.workflows/orchestration/honest-control-redraw/PLAN.md` phase 3. Source: `.workflows/plan/honest-control-redraw/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: The twin yardsticks: M0221 and M0225

**Plan set:** `HONEST_CONTROL_REDRAW_PLAN.md`
**Analysis:** `docs/analyzer/20261019-181712-C4K9_code_analyzer.md`
**Satisfies:** R2 (re-draw the mis-shaped arms as amendments under the existing ids), R3 (re-state
the two margins in `trial_funding.mwr`, including a margin that worsens), R4 (the arm's own `supersedes` declaration — without it phase 2's D17 rule fires on nothing and the method stays blocked after the measurement)
**Depends on:** Phase 1 — `engine/src/seer_engine/lab/control_draw.py` (the matched-draw rule),
consumed unchanged
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab/methods`

---

## Goal

After this phase, M0221 and M0225 each hold one honestly-shaped blind control for their 50-name
cap-weighted book — `M0221-C50-PLC` and `M0225-C50-PLC` — recorded as amendments under the
existing method ids, with no new method id, no moved `config_digest` and no test-window look. The
two arms are drawn by the *identical* rule under the *identical* hash namespace and seed, so the
M0221→M0225 twin comparison still measures the share-count data fix and nothing else. The two
margins that were quoted against `R50` (a control that trades 0.21x and 0.19x the book it
controls) are re-stated against a control that trades like the book.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts.

**Deletes:** nothing. No line is removed from either method file.

**Renames:** nothing.

**Creates:**

| Symbol | File | Kind |
|---|---|---|
| `AMENDED = date(2026, 10, 19)` | `m0221_cap_weighted_top_n.py` | module constant |
| `DRAW_KEY = "M0221"` | `m0221_cap_weighted_top_n.py` | module constant |
| `_check_control` | `m0221_cap_weighted_top_n.py` | function |
| `MatchedCapTopAllocator` (**allocator id `M0221-A1`**) | `m0221_cap_weighted_top_n.py` | class |
| `MATCHED` | `m0221_cap_weighted_top_n.py` | allocator instance |
| `_a` | `m0221_cap_weighted_top_n.py` | function |
| `MATCHED_AMENDMENT` | `m0221_cap_weighted_top_n.py` | `Amendment`, becomes M0221 **seq 1** |
| candidate `M0221-C50-PLC` | `m0221_cap_weighted_top_n.py` | `Candidate` |
| `AMENDED = date(2026, 10, 19)` | `m0225_cap_weighted_top_n_repaired.py` | module constant |
| `MatchedRepairedCapTopAllocator` (**allocator id `M0225-A2`**) | `m0225_…repaired.py` | class |
| `MATCHED` | `m0225_…repaired.py` | allocator instance |
| `_a` | `m0225_…repaired.py` | function |
| `MATCHED_AMENDMENT` | `m0225_…repaired.py` | `Amendment`, becomes M0225 **seq 2** |
| candidate `M0225-C50-PLC` | `m0225_…repaired.py` | `Candidate` |

Two `method_amendments` rows (`M0221` seq 1, `M0225` seq 2), two `trials` rows and two
`trial_funding` rows are appended to `/home/miftah/seer/lab/lab.sqlite`.

**Signature changes:** none. `CapTopParams`, `CapTopAllocator`, `draw`, `sized_pool`, `weights`,
`_check`, `_gate`, `_v`, `CAPTOP`, `SW`, `ADDED`, `DV_N`, `WEIGHTINGS`, `PICKS` and
`RepairedCapTopAllocator` are all **untouched**, byte for byte. `E100_AMENDMENT` is untouched,
byte for byte, and stays first in `M0225.amendments`.

**Requires (from earlier phases):** Phase 1's `engine/src/seer_engine/lab/control_draw.py`,
exporting `previous_decision_date`, `matched_names` and `lookback_for`, and Phase 1's
`backtest.dev.Candidate.supersedes` field. **Reconciled 2026-10-19 against Phase 1's actual
module**; the signatures are restated below and the call sites in Step 2 already use them.

**Leaves alone (owned by others):** `lab/control_draw.py` (Phase 1 — consumed, never edited),
`lab/control_shape.py` and `lab/hardgate.py` and `commands/lab.py` (Phase 2),
`m0047_market_value_residual.py` (Phase 4), `m0201_*`/`m0202_*` (Phase 5), `m0208_*` (Phase 6),
`m0215_*` (Phase 7), `lab stage`, `web/data/lab.json`, `lab insight`, the handover doc (Phase 8),
and the test window in every form.

---

## The contract from Phase 1, as Phase 1 actually wrote it

This phase calls three names from `engine/src/seer_engine/lab/control_draw.py`. Reconciled
2026-10-19 against Phase 1's own plan; these are the real signatures, not an assumption.

```python
def previous_decision_date(data_date: date, cadence: str = "monthly") -> date:
    """The ``data_date`` of the decision before the one being made at ``data_date``.

    Off the published NYSE calendar and nothing else -- it takes no History and never returns
    None. Under a monthly cadence ``data_date`` is the last session of a calendar month, so this
    is the last session strictly before the first calendar day of ``data_date``'s own month.
    Raises on a cadence outside ``CADENCES``.
    """


def matched_names(
    *,
    pool: Sequence[str],          # today's eligible pool, the real arm's own, any order
    held: AbstractSet[str],       # what the control holds coming into this session
    real_now: Sequence[str],      # the real arm's selection at this data date
    real_prev: Sequence[str],     # the real arm's selection at the previous decision
    tag: str,                     # the hash namespace -- the BOOK's method id
    seed: int,
    data_date: date,
) -> list[str]:
    """``len(real_now)`` names from ``pool``, entering as many as ``real_now`` entered.

    ``keep_n = len(real_now) - churn(real_now, real_prev)``; that many of ``held & pool`` in the
    DATE-FREE keep order, then the book is filled from the month-keyed entry order of the names
    the control does NOT hold -- and only once those run out, from the holdings it is dropping.
    Returned in the month-keyed order. Ties break on the symbol.
    """


def lookback_for(inner: int) -> int:
    """``inner + PREVIOUS_DECISION_BARS`` (26), for an allocator that reads twice."""
```

**Three differences from this phase's first draft, all mechanical and all applied below.** The
helper is `matched_names`, not `matched_book` (which takes a `select` callable this chassis has
no use for). The keyword is `tag`, not `key`, and `real_now` / `real_prev`, not `now` / `prev`.
And `previous_decision_date` takes only the date, returns a `date` and never `None`, so the
`prev_date is not None` branch and the `prepared.history.get("SPY")` argument both go. `PREV_GAP`
is replaced by `control_draw.lookback_for`, whose `PREVIOUS_DECISION_BARS` is 26 rather than 24 —
measured by Phase 1 against the whole dev calendar rather than estimated here.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py` | modify | docstring paragraph; three constants after `:73`; `_check_control` after `:124`; `MatchedCapTopAllocator` + `MATCHED` after `:240`; `_a` + `MATCHED_AMENDMENT` after `:249`; `amendments=` on `METHOD` at `:315` |
| `engine/src/seer_engine/lab/methods/m0225_cap_weighted_top_n_repaired.py` | modify | docstring paragraph; `AMENDED` after `:54`; import at `:48`; `MatchedRepairedCapTopAllocator` + `MATCHED` after `:63`; `_a` + `MATCHED_AMENDMENT` after `:98`; `amendments=` at `:162` |
| `.workflows/plan/honest-control-redraw/phase-3-results.md` | create | the two shape readings and the two re-stated margins, for Phase 8 to collect |
| `/home/miftah/seer/lab/lab.sqlite` | append (by `lab run --amend` only) | 2 `method_amendments`, 2 `trials`, 2 `trial_funding` rows |

---

## Implementation Steps

### Step 1: M0221 — the three constants and the control's params check

**File:** `engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py:72-74` (after `PICKS`)
and `:124` (after `_gate`).

**Change:** add the amendment's own `added` date and the hash namespace that M0225 will inherit.
Then a params check that says out loud that the matched draw is a control. `ADDED`, `DV_N`,
`WEIGHTINGS` and `PICKS` are not touched. The previous-decision lookback slack is **not** a
constant of this file: `control_draw.lookback_for` owns it, at `PREVIOUS_DECISION_BARS = 26`,
measured by Phase 1 over the whole dev calendar.

**Code** — insert immediately after line 75 (`PICKS = ("size", "random")`):

```python

#: The matched-draw amendment's own date. The originals were written on 2026-10-18; this block
#: was written on 2026-10-19 and pre-registered by the commit that added it.
AMENDED = date(2026, 10, 19)

#: The hash namespace of every blind draw on this chassis. It is the literal ``draw`` already
#: keys on, and M0225 deliberately reuses it (its own ``R50`` does, through ``draw``) so the two
#: blind books hold the same names wherever both stores size the same company. Changing it would
#: put a draw difference on top of the data difference the twin exists to measure.
DRAW_KEY = "M0221"
```

**Code** — insert immediately after line 124 (the blank line following `_gate`), before
`def draw(...)` at `:127`:

```python
def _check_control(params: object) -> CapTopParams:
    """``_check``, plus the one thing a control may not be: a book that ranks on size.

    The matched draw differs from ``R50`` in its allocator id and in nothing else -- the params
    are byte-identical -- so the params must still say ``pick="random"``. Saying ``"size"`` would
    record a configuration whose text claims a size ranking the allocator never performs.
    """
    p = _check(params)
    if p.pick != "random":
        raise ValueError(f"the matched draw is a control: pick must be 'random', got {p.pick!r}")
    return p
```

**Impact:** none on any recorded digest — `config_text` reads `c.rules`, `c.allocator.id` and
`c.params` only, and no params dataclass gains, loses or reorders a field. `_canon` enumerates
`dataclasses.fields(CapTopParams)`, which is unchanged.

---

### Step 2: M0221 — the matched-draw allocator

**File:** `engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py:240` — insert
immediately after `CAPTOP = CapTopAllocator()` and before the blank lines preceding
`SW = ("SPY", 200)` at `:242`.

Also add the import of the helper to the import block (after line 61,
`from seer_engine.lab.method import Method`):

```python
from seer_engine.lab import control_draw
```

**Change:** a new allocator class, subclassing `CapTopAllocator` exactly the way M0225's
`RepairedCapTopAllocator` already does, with a new id. It overrides `lookback`, `targets` and
`targets_prepared` and adds two private helpers; it inherits `symbols`, `holds`, `uses_members`,
`prepare`, `prepare_market` and `market_fields` unchanged.

**Code:**

```python
class MatchedCapTopAllocator(CapTopAllocator):
    """The same blind book as ``R50``, re-keyed at the real arm's OWN churn instead of never.

    ``R50`` draws its fifty names in ``draw(seed, symbol)``, a hash with no date term, so its
    book changes only when the pool does. Measured on the dev window: 76 trades against C50's
    360 and 0.222 turnover against 0.445 -- 0.21x and 0.50x, which ``lab control`` refuses (D17).
    A control that trades a fifth as often pays a fifth of the fees, so C50's recorded 1.09-point
    deficit to R50 was quoted against an opponent running downhill, and the deficit is not
    evidence about size ranking. M0243's own file records the same error with the sign flipped --
    its author saw a sticky draw trade 41 times in twenty years, re-drew monthly by hand, and
    overshot to 3.01x. The re-key period is not something to choose; it is something to derive.

    So this allocator keeps everything about R50 except that period, and takes it from the book
    it controls. At each monthly decision it recomputes the real arm's own selection -- the top
    ``top`` of the day's sized pool -- at this data date and at the previous decision's data date
    (``control_draw.previous_decision_date``), counts the names that entered, keeps that many
    fewer of its own holdings in R50's date-free hash order, and draws the rest fresh from the
    same eligible pool in a hash order seeded on the current month
    (``control_draw.matched_book``). The entry count per rebalance is matched by construction, so
    the trade axis is ~1.00 analytically rather than by tuning -- which is the whole reason the
    rule lives in one shared module and is not re-invented per method file.

    **It is still blind.** Nothing it reads about a name decides whether that name is drawn. The
    only thing it takes from the real arm is HOW MANY names changed this month, which is shape,
    not identity. The weighting is R50's unchanged: the drawn names' own market values,
    cap-weighted with the same 10% ceiling, so the only difference between R50 and this arm is
    the draw's re-key period and nothing else at all.

    **The hash namespace** is ``DRAW_KEY``, not the allocator id, for the same reason ``draw``
    hardcodes "M0221": M0225's twin of this arm inherits this class and must draw the same names
    wherever both stores size the same company, or the before-and-after would carry a draw change
    on top of the data change it exists to measure.

    No share counts (the history-only path): no size, so no churn to match and no targets.
    """

    id = "M0221-A1"

    def lookback(self, params: Any) -> int:
        """One month more than the real arm's: ``DV_N`` bars of trading value at the PREVIOUS
        decision's data date. ``control_draw.lookback_for`` adds the 26 bars Phase 1 measured as
        the widest gap on the dev calendar, so 86 at the default -- far inside the 473-bar smoke
        fixture ``test_allocator_contract`` runs."""
        p = _check_control(params)
        return max(control_draw.lookback_for(DV_N), 0 if p.trend is None else p.trend[1])

    def _selection(self, prepared: CapTopPrepared, members: AbstractSet[str], at: date,
                   p: CapTopParams) -> tuple[tuple[str, ...], dict[str, float]]:
        """The real arm's own book at ``at``, and the sized pool it was drawn from.

        Membership is the caller's -- today's -- at both dates: the index's composition today is
        known today, so reading it at an earlier date adds no look-ahead, and the prices and share
        counts are still read only as of ``at``.
        """
        pool = sized_pool(prepared, members, at)
        if not pool:
            return (), {}
        return tuple(sorted(pool, key=lambda s: (-pool[s], s))[: p.top]), pool

    def _matched(self, prepared: CapTopPrepared, members: AbstractSet[str], data_date: date,
                 held: frozenset[str], p: CapTopParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        now, pool = self._selection(prepared, members, data_date, p)
        if not pool:
            return ()
        prev, _ = self._selection(
            prepared, members, control_draw.previous_decision_date(data_date), p
        )
        picks = control_draw.matched_names(
            pool=tuple(sorted(pool)),
            held=held,
            real_now=now,
            real_prev=prev,
            tag=DRAW_KEY,
            seed=p.seed,
            data_date=data_date,
        )
        out: list[Target] = []
        for s, w in zip(picks, weights([pool[s] for s in picks], p), strict=True):
            if w is None:
                continue
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no size, no churn to match and no target."""
        _check_control(params)
        return ()

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CapTopPrepared):
            raise TypeError(f"prepared must be CapTopPrepared, got {type(prepared).__name__}")
        return self._matched(prepared, members, data_date, held, _check_control(params))


MATCHED = MatchedCapTopAllocator()
```

**Impact:**

- `CapTopAllocator.id` stays `"M0221"`, so every recorded M0221 and M0225 trial keeps its digest.
- `test_allocator_ids_are_unique_across_methods` maps each allocator id to one object. `M0221-A1`
  is used by exactly one candidate (`M0221-C50-PLC`) through the single `MATCHED` instance; M0225
  subclasses the class but never instantiates *this* class. Green.
- `test_allocator_contract` drives `prepare(history)` (market `None`) and asserts a market-aware
  allocator targets nothing there. `targets` returns `()` and `targets_prepared` is not reached by
  the kit, so the new arm behaves exactly as M0221's six existing arms do under that test.
  `assert_p4_identity` and `assert_no_lookahead` pass trivially, as they do today.
- Lookback 86 ≤ 473 (the smoke fixture's size, and absolute). `lookback_for(DV_N)` is
  `DV_N + 26`; `PREVIOUS_DECISION_BARS` lives in `control_draw` so nine method files cannot each
  guess a different slack.
- `previous_decision_date` never returns `None` and reads no `History`, so there is no
  "previous decision not on hand" branch. Before the store's first month the earlier
  `_selection` simply returns `((), {})`, `real_prev` is empty, `churn` is `len(real_now)` and
  the whole book is drawn fresh -- which is what a kickoff session should do.

---

### Step 3: M0221 — the Amendment block

**File:** `engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py:249` — insert after
`_v` and before `METHOD = Method(` at `:251`. Also extend the import at `:61` from
`from seer_engine.lab.method import Method` to
`from seer_engine.lab.method import Amendment, Method`.

**Code:**

```python
def _a(suffix: str, allocator: Any, params: CapTopParams, rationale: str,
       supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate: its own ``added`` date, its own allocator and the declaration of
    which recorded arm it replaces, otherwise ``_v``.

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``). It is DECLARED and never
    inferred from the target, and it is outside ``config_digest`` because ``config_text`` names
    its three attributes by hand. An arm that declares nothing retires nothing, so leaving this
    off would leave M0221 blocked after the measurement was taken."""
    return Candidate(id=f"M0221-{suffix}", family="M0221", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=AMENDED,
                     owner_inputs=(), supersedes=supersedes)


MATCHED_AMENDMENT = Amendment(
    added=AMENDED,
    why=(
        "R50, the control C50's margin is quoted against, trades 0.21x and turns over 0.50x what "
        "C50 does, so D17 refuses it; re-draw it at C50's own monthly churn and re-state the gap"
    ),
    hypothesis=(
        "Written before any result. C50 earned 5.63% a year of the owner's money on the dev "
        "window and R50 earned 6.72% against the same 7.19% SPY total return, so the blind draw "
        "currently BEATS the book by 1.09 points -- and R50 got there on 76 trades where C50 "
        "paid for 360. R50's hash has no date term, so it drew fifty names once and held them "
        "for twenty years whatever the market did; the only fees it ever paid were the ones "
        "membership forced on it. C50-PLC is the same fifty-name cap-weighted blind book with "
        "one thing changed: the number of names it re-draws each month is C50's own number of "
        "entrants that month, taken from C50's calendar rather than chosen by hand. Prediction, "
        "and the direction is the point: the honest control trades about five times as often, "
        "pays those fees, and therefore earns LESS than R50 did, so C50's deficit NARROWS -- to "
        "somewhere between 0 and 1 point, and possibly past zero into a lead. Second prediction, "
        "about shape rather than money, and the one that decides whether the first is readable "
        "at all: C50-PLC lands inside 0.80x-1.25x of C50 on both trades and turnover, which is "
        "what makes the re-stated gap evidence instead of a handicap. Success here is a yardstick "
        "whose control is honest, not an arm that wins: no arm of this method is for promotion."
    ),
    expected_failure=(
        "The fee channel is small in absolute terms and the identity channel may swamp it. C50 "
        "turns over only 0.445 of the account a year, so matching it raises the control's "
        "turnover by about 0.22 a year, and Gotrade's bill on that is tens of basis points, not "
        "a point -- while re-keying the draw monthly changes WHICH names the control holds for "
        "twenty years, and a draw re-sampled every month converges on the sized pool's own mean "
        "return instead of resting on one lucky 1996 sample. If that mean is above what R50's "
        "single sticky draw happened to earn, the matched control earns MORE, C50's deficit "
        "WIDENS rather than narrows, and the pre-registered direction is simply wrong. That is "
        "the finding and it is reported as one; it is not re-drawn for. Second, the shape may "
        "miss on the turnover axis alone: E50 holds C50's exact names and trades C50's exact 360 "
        "times, yet turns over 1.60x as much, because a flatter weight vector crosses the resize "
        "band more often -- and a blind draw from the sized pool is flatter than the top fifty "
        "are, since it rarely holds a name big enough for the 10% ceiling to bind. If C50-PLC "
        "clears the trade axis and lands above 1.25x on turnover, the matched-draw rule does not "
        "settle this chassis and the honest answer is to say so rather than to re-draw. Third, "
        "the previous decision's selection is recomputed with TODAY's membership, so a name that "
        "joined the index in between is counted as a non-entrant and the matched entry count "
        "reads slightly low; the effect is one or two names a year on a 50-name book."
    ),
    candidates=(
        _a("C50-PLC", MATCHED, CapTopParams(50, pick="random", seed=1, trend=None),
           "Placebo, shape-matched: the same fifty-name cap-weighted blind book, hash-drawn at "
           "C50's own monthly churn instead of once and forever",
           supersedes=("M0221-R50",)),
    ),
)
```

Then, at `:315` (between `seen_keys=(...)` closing at `:315` and the method's closing `)` at
`:316`), add the amendments tuple:

```python
    amendments=(MATCHED_AMENDMENT,),
```

so the tail of `METHOD` reads:

```python
    seen_keys=(
        "concept:cap-weighted-top-n",
        "concept:market-shape-yardstick-real-cap",
    ),
    amendments=(MATCHED_AMENDMENT,),
)
```

**Impact and the four checks this block has to pass:**

1. **`Method.__post_init__` id uniqueness.** `M0221-C50-PLC` is not among C50, C100, C20, C50-SW,
   E50, R50. ✓
2. **`Method.__post_init__` configuration uniqueness.** `config_text` is
   `rules=<monthly-hold-frac-gotrade canon>` + `allocator=<M0221-A1>` +
   `params=CapTopParams(top=50,weighting='cap',cap=0.1,pick='random',seed=1,trend=None)`.
   R50's is identical except `allocator=<M0221>`. Different text, different digest. ✓ The same
   argument covers `trials`' global `UNIQUE(config_digest, window)`.
3. **D17 classification.** The rationale lower-cases to `"placebo, shape-matched: the same
   fifty-name cap-weighted blind book, hash-drawn at c50's own monthly churn instead of once and
   forever"`. It contains `"placebo"` and `"hash-drawn"` (both `DRAW_MARKERS`) and none of
   `DOSE_MARKERS` — not `"dose-response"`, not `"dose:"`, not `"and not since"`, not
   `"and none since"`, not `"does the date do any work"`, not `"on the date itself"`. `kind_of`
   tests dose first and finds nothing, then draw and returns `KIND_PLACEBO`. ✓ **It must be
   shape-checked. Wording it out of the check is forbidden (plan invariant 3).**
4. **`resolve_target` walk for `M0221-C50-PLC`,** against
   `METHOD.all_candidates() = (C50, C100, C20, C50-SW, E50, R50, C50-PLC)`:
   - `declared_target` → `getattr(c, "controls", None)` is `None` (no `Candidate.controls` field
     exists). Falls through.
   - `_eligible_targets` drops the arm itself (`M0221-C50-PLC`) and every arm whose `kind_of` is
     placebo or dose. R50's rationale is *"Control: 50 members in a fixed size-blind **hash
     order**, cap-weighted, no switch"* → `KIND_PLACEBO` → dropped. C50, C100, C20, C50-SW and
     E50 carry no marker of any kind → `KIND_NONE` → all eligible. **In particular the stem arm
     `M0221-C50` is itself eligible: its rationale is "Top 50 members by market value,
     cap-weighted with a 10% ceiling, no switch", which contains no `DRAW_MARKERS`, no
     `DOSE_MARKERS` and no `ABLATION_MARKERS`.**
   - `stem = "M0221-C50-PLC".rsplit("-", 1)[0] = "M0221-C50"`, which is not the control's own id
     and *does* name an eligible arm → **returns `("M0221-C50", RUNG_STEM)`**, the strongest rung.
     The `declared-idea` and `first-declared` rungs are never reached, so no guess is made. ✓

---

### Step 4: M0225 — the twin allocator and its Amendment block

**File:** `engine/src/seer_engine/lab/methods/m0225_cap_weighted_top_n_repaired.py`.

**(a) Import, `:48`.** Change

```python
from seer_engine.lab.methods.m0221_cap_weighted_top_n import CapTopAllocator, CapTopParams
```

to

```python
from seer_engine.lab.methods.m0221_cap_weighted_top_n import (
    CapTopAllocator,
    CapTopParams,
    MatchedCapTopAllocator,
)
```

**(b) The amendment's date, after `:54` (`ADDED = date(2026, 10, 18)`):**

```python
AMENDED = date(2026, 10, 19)
```

**(c) The twin allocator, after `:63` (`CAPTOP = RepairedCapTopAllocator()`) and before
`SW = ("SPY", 200)` at `:65`:**

```python
class MatchedRepairedCapTopAllocator(MatchedCapTopAllocator):
    """M0221's matched blind draw, recorded under M0225: the same rule on the repaired size data.

    It inherits ``DRAW_KEY`` ("M0221") on purpose, exactly as ``RepairedCapTopAllocator`` inherits
    ``draw``: the kept half of each month's book is ordered by the same date-free hash M0221's
    twin uses, the fresh half by the same month-seeded one, and the seed is the same 1. So
    wherever both stores size a company the same way the two placebos hold the same names, and
    the before-and-after still measures the share-count repair and nothing else. Where the two
    books do differ, they differ because the repaired store ranks the real arm differently and
    therefore hands the control a different number of names to re-draw -- which is the data fix
    showing up in the control's shape, and is exactly what this twin is for.
    """

    id = "M0225-A2"


MATCHED = MatchedRepairedCapTopAllocator()
```

**(d) The amendment block, after `:98` (the closing `)` of `E100_AMENDMENT`) and before
`METHOD = Method(` at `:101`.** `E100_AMENDMENT` above it is **not touched**:
`runner.pending_amendment` compares the recorded seq-1 row against it field by field
(`added`, `why`, `hypothesis`, `expected_failure`, each `.strip()`-ed), and any edit makes
`lab run --amend` refuse the whole method.

```python
def _a(suffix: str, allocator: object, params: CapTopParams, rationale: str,
       supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate: its own ``added`` date, its own allocator and its declaration."""
    return Candidate(id=f"M0225-{suffix}", family="M0225", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=AMENDED,
                     owner_inputs=(), supersedes=supersedes)


MATCHED_AMENDMENT = Amendment(
    added=AMENDED,
    why=(
        "R50, the control C50's margin is quoted against, trades 0.19x and turns over 0.42x what "
        "C50 does, so D17 refuses it; re-draw it at C50's own monthly churn, by M0221's identical "
        "rule, seed and hash namespace, so the twin still measures only the share-count repair"
    ),
    hypothesis=(
        "Written before any result, and in the same words as M0221's twin of this block because "
        "that is the point of the pair. On the repaired store C50 earned 5.85% a year of the "
        "owner's money and R50 earned 6.74% against the same 7.19% SPY total return, so the "
        "blind draw BEATS the book by 0.89 points -- on 73 trades against C50's 375. R50's hash "
        "has no date term, so it drew fifty names once and held them for twenty years. C50-PLC "
        "is the same fifty-name cap-weighted blind book with one thing changed: the number of "
        "names it re-draws each month is C50's own number of entrants that month. Prediction: "
        "the honest control trades about five times as often, pays those fees, and therefore "
        "earns LESS than R50 did, so C50's deficit NARROWS -- to somewhere between 0 and 0.9 "
        "points, possibly past zero into a lead. Second prediction, on shape: C50-PLC lands "
        "inside 0.80x-1.25x of C50 on both trades and turnover. Third, and the one only this "
        "twin can make: the M0221 and M0225 matched placebos differ from each other by LESS than "
        "their two real arms do, because a blind draw is indifferent to which of the pool's "
        "companies now has a known share count and the size-ranked arm is not -- so the gap "
        "between the two C50-PLC arms is close to zero and whatever separates M0221-C50 from "
        "M0225-C50 is the data fix. No arm of this method is for promotion."
    ),
    expected_failure=(
        "The same two ways M0221's twin can be wrong, and one of its own. First, the fee channel "
        "is small: C50 turns over 0.457 of the account a year, so matching it costs the control "
        "tens of basis points, while re-keying the draw monthly changes which names it holds for "
        "twenty years and a continuously re-sampled draw converges on the sized pool's mean "
        "return rather than one lucky 1996 sample. If that mean is above R50's, the matched "
        "control earns MORE and C50's deficit WIDENS. That is the finding, not a reason to "
        "re-draw. Second, the shape may miss on turnover alone: E50 holds C50's exact names and "
        "trades its exact 375 times yet turns over 1.68x as much, because a flatter weight "
        "vector crosses the resize band more often, and a blind draw from the sized pool is "
        "flatter than the top fifty are. Third, and only here: the repaired store gives sizes to "
        "Visa, Mastercard, Meta, Berkshire, Comcast, UPS, Ford and Alphabet, which widens the "
        "sized pool, so this placebo draws from a slightly larger pool than M0221's does and the "
        "two matched arms may separate by more than the two real arms do -- which would mean the "
        "blind draw is MORE sensitive to the repair than the size ranking is, and would make the "
        "whole before-and-after harder to read rather than easier."
    ),
    candidates=(
        _a("C50-PLC", MATCHED, CapTopParams(50, pick="random", seed=1, trend=None),
           "Placebo, shape-matched: M0221-C50-PLC's rule unchanged on the repaired store -- the "
           "same fifty-name cap-weighted blind book, hash-drawn at C50's own monthly churn",
           supersedes=("M0225-R50",)),
    ),
)
```

**(e) The amendments tuple, `:162`.** Change

```python
    amendments=(E100_AMENDMENT,),
```

to

```python
    amendments=(E100_AMENDMENT, MATCHED_AMENDMENT),
```

**Order is load-bearing.** `method_amendments` is append-only and contiguous and
`pending_amendment` returns `method.amendments[len(recorded)]`; the lab has recorded exactly one
row for M0225 (seq 1, 2026-10-18, E100). With E100 first, `len(recorded) == 1` selects
`MATCHED_AMENDMENT` and it records as **seq 2**. Putting it first would make the lab compare the
recorded E100 row against this block and refuse.

**Impact and the same four checks:**

1. **Id uniqueness:** `M0225-C50-PLC` is new among C50, C100, C20, C50-SW, E50, R50, E100. ✓
2. **Configuration uniqueness:** `allocator=<M0225-A2>` against R50's `<M0225>` and
   M0221-C50-PLC's `<M0221-A1>`, with identical params. Three distinct digests. ✓
   `test_allocator_ids_are_unique_across_methods`: `M0225-A2` belongs to the single `MATCHED`
   instance in this file; `M0221-A1` belongs to M0221's. ✓
3. **D17 classification:** the rationale contains `"placebo"` and `"hash-drawn"` and no
   `DOSE_MARKERS`. Note it names `M0221-C50-PLC` — that is prose, not a resolution mechanism, and
   `resolve_target` never reads another method's ids. ✓
4. **`resolve_target` walk for `M0225-C50-PLC`,** against
   `(C50, C100, C20, C50-SW, E50, R50, E100, C50-PLC)`:
   - no `controls` attribute → no declared rung.
   - `_eligible_targets` drops the arm itself and R50 (*"…in a fixed size-blind **hash order**,
     cap-weighted"* → `KIND_PLACEBO`). C50, C100, C20, C50-SW, E50 and E100 carry no marker.
     **`M0225-C50`'s rationale is "M0221-C50 unchanged: top 50 by market value, cap-weighted, 10%
     ceiling, no switch" — no `DRAW_MARKERS`, no `DOSE_MARKERS`, no `ABLATION_MARKERS`, so the
     stem arm is itself eligible.**
   - `stem = "M0225-C50"` names an eligible arm → **`("M0225-C50", RUNG_STEM)`**. ✓

---

### Step 5: the two runs

Environment, identical for every command below. Note the lab database and the research store are
the **main checkout's** (worktrees have neither), while `PYTHONPATH` is the **worktree's** source,
so the method files that run are this branch's.

```bash
export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite
export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
export PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src
PY=/home/miftah/seer/engine/.venv/bin/python
WT=/home/miftah/.worktrees/seer/honest-control-redraw
OUT=/tmp/claude-1000/-home-miftah-seer/phase3
mkdir -p "$OUT"
```

**Never judge a `lab` command by a piped exit code** (`grep -v` would own the status, and a
retried `lab` command can double-write). Every run below redirects to a file and reads `$?` on its
own, then the file is read with `cat`.

**5a. Pre-registration commit for M0221 — by pathspec, before the run.**

```bash
cd "$WT"
git add -- engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py
git commit -m "lab: M0221 amendment 1 pre-registered -- C50's blind control re-drawn at C50's own churn" \
           -m "R50 trades 0.21x and turns over 0.50x what C50 does, so D17 refuses it and C50's
recorded 1.09-point deficit to it was quoted against an opponent paying a fifth of the fees. The
new arm is R50 with one thing changed: the number of names it re-draws each month is C50's own
number of entrants, taken from C50's calendar. Direction pre-registered before any result: the
honest control earns less and the deficit narrows." \
           -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git status --porcelain -- engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py  # must be empty
```

**5b. Hash the database, run M0221, hash it again.**

```bash
git -C /home/miftah/seer hash-object lab/lab.sqlite      # record: expect 3969f1fa… before the first run
$PY -m seer_engine lab run M0221 --amend > "$OUT/m0221_run.txt" 2>&1; echo "exit=$?"
cat "$OUT/m0221_run.txt"
git -C /home/miftah/seer hash-object lab/lab.sqlite      # record: it WILL move; that is the record being written
```

Exit 0 is ok, 2 means the lab's rules refused the request (read the message; do not retry blind),
1 is an error. The run prints its own control-shape reading at the end (`commands/lab.py:1751`)
and refuses nothing there (D15) — read it, but the authoritative reading is 5d.

**5c. Gate: does M0221-C50-PLC sit inside the match band?**

```bash
$PY -m seer_engine lab control M0221 > "$OUT/m0221_control.txt" 2>&1; echo "exit=$?"
cat "$OUT/m0221_control.txt"
```

`M0221-C50-PLC` must read `ok` against `M0221-C50` on **both** axes — `band_verdict` returns `OK`
only inside `WARN_BAND = (0.80, 1.25)`, inclusive at the edges, and `findings` takes the `worst`
of the two. A `warn` is **not** good enough here: R1's bar is the match band, not the refuse band.

**If it is `warn` or `refuse`: STOP.** Write the two measured ratios and the reason into
`phase-3-results.md`, do not commit or run M0225's block, do not touch the seed, do not re-draw
for a better number (plan invariant 4; design §4). Report to the coordinator that the matched-draw
rule does not settle the cap-weighted chassis, and say which axis missed and by how much — a
turnover-only miss and a trade-axis miss mean different things about the rule.

**5d. Only if 5c is `ok`: pre-register and run M0225.**

```bash
cd "$WT"
git add -- engine/src/seer_engine/lab/methods/m0225_cap_weighted_top_n_repaired.py
git commit -m "lab: M0225 amendment 2 pre-registered -- the twin of M0221's re-drawn control" \
           -m "The same matched-draw rule, the same seed and the same hash namespace as
M0221-C50-PLC, so the before-and-after still measures the share-count repair and nothing else.
R50 trades 0.19x and turns over 0.42x what M0225-C50 does. Direction pre-registered before any
result: the honest control earns less and C50's 0.89-point deficit narrows." \
           -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git status --porcelain -- engine/src/seer_engine/lab/methods/m0225_cap_weighted_top_n_repaired.py

git -C /home/miftah/seer hash-object lab/lab.sqlite
$PY -m seer_engine lab run M0225 --amend > "$OUT/m0225_run.txt" 2>&1; echo "exit=$?"
cat "$OUT/m0225_run.txt"
git -C /home/miftah/seer hash-object lab/lab.sqlite

$PY -m seer_engine lab control M0221 M0225 > "$OUT/control_both.txt" 2>&1; echo "exit=$?"
cat "$OUT/control_both.txt"
```

**Impact:** two `method_amendments` rows (M0221 seq 1, M0225 seq 2), two `trials` rows and two
`trial_funding` rows. All three tables carry append-only triggers on update *and* delete: once
either run lands it is permanent, which is why the whole pre-registration is in the commit that
precedes it.

---

### Step 6: write the numbers down

**File:** `.workflows/plan/honest-control-redraw/phase-3-results.md` — **this is the single place
Phase 8 collects this phase's numbers from.** Nothing else in this phase writes a number anywhere
a later reader will look: no `lab note`, no `lab insight`, no edit to the plan index, no
`lab stage`.

Re-derive every figure read-only, so the inspection itself never migrates the database:

```bash
sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" "
SELECT t.candidate_id, t.n, t.trades, round(t.turnover, 4),
       round(f.mwr * 100, 2) AS mwr_pct, round(f.spy_tr_mwr * 100, 2) AS spy_pct
FROM trials t JOIN trial_funding f ON f.trial_n = t.n
WHERE t.window = 'dev' AND t.method_id IN ('M0221','M0225')
ORDER BY t.n;"

sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" "
SELECT method_id, seq, added, run_at, substr(why,1,60) FROM method_amendments
WHERE method_id IN ('M0221','M0225') ORDER BY method_id, seq;"

sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" "
SELECT count(*) FROM trials WHERE window = 'test';"   # must be unchanged: no look was spent
```

The file carries exactly this, filled in:

```markdown
# Phase 3 results — M0221 and M0225, the twin yardsticks

Measured <date>. Lab database `git hash-object`: <before> -> <after>.
Money is `trial_funding.mwr`. SPY TR on the same deposits is 7.19%/yr for every row.

## Shape (`lab control M0221 M0225`)

| method | control | controls | rung | trades x | turnover x | verdict |
|---|---|---|---|---|---|---|
| M0221 | M0221-R50     | M0221-C50 | sibling-stem | 0.21 | 0.50 | refuse (the old arm) |
| M0221 | M0221-C50-PLC | M0221-C50 | sibling-stem | ?    | ?    | ? |
| M0225 | M0225-R50     | M0225-C50 | sibling-stem | 0.19 | 0.42 | refuse (the old arm) |
| M0225 | M0225-C50-PLC | M0225-C50 | sibling-stem | ?    | ?    | ? |

## Money (`trial_funding.mwr`, %/yr)

| book | old control | old margin | new control | new margin | direction held? |
|---|---|---|---|---|---|
| M0221-C50 5.63 | R50 6.72 | **-1.09** | C50-PLC ? | ? | pre-registered: narrows |
| M0225-C50 5.85 | R50 6.74 | **-0.89** | C50-PLC ? | ? | pre-registered: narrows |

## The twin reading

M0221-C50-PLC ? vs M0225-C50-PLC ?: the two blind books differ by ? points, against the ?-point
gap between M0221-C50 and M0225-C50. One sentence on whether the share-count repair moved the
book more than it moved its own control.

## Verdicts

One sentence per method: did the standing verdict survive its honest control?
Test-window looks before and after: 4 -> 4.
```

Commit it by pathspec:

```bash
cd "$WT"
git add -- .workflows/plan/honest-control-redraw/phase-3-results.md
git commit -m "lab: M0221 and M0225 re-drawn controls recorded -- the measured shapes and margins" \
           -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Verification

**Build (imports, construction, `Method.__post_init__`):**

```bash
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
from seer_engine.lab.method import config_digest
import seer_engine.lab.methods.m0221_cap_weighted_top_n as a
import seer_engine.lab.methods.m0225_cap_weighted_top_n_repaired as b
for m in (a.METHOD, b.METHOD):
    print(m.id, [c.id for c in m.all_candidates()], len(m.amendments))
# the two new arms differ from R50 only by allocator id, and from each other too
for m in (a.METHOD, b.METHOD):
    d = {c.id: config_digest(c) for c in m.all_candidates()}
    assert len(set(d.values())) == len(d), m.id
    print(m.id, "R50", d[f"{m.id}-R50"][:12], "C50-PLC", d[f"{m.id}-C50-PLC"][:12])
PY
```

**Resolution and classification, before any run:**

```bash
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
/home/miftah/seer/engine/.venv/bin/python - <<'PY'
from seer_engine.lab import control_shape as cs
import seer_engine.lab.methods.m0221_cap_weighted_top_n as a
import seer_engine.lab.methods.m0225_cap_weighted_top_n_repaired as b
for m in (a.METHOD, b.METHOD):
    arms = m.all_candidates()
    plc = [c for c in arms if c.id.endswith("-C50-PLC")][0]
    assert cs.kind_of(plc) == cs.KIND_PLACEBO, (plc.id, cs.kind_of(plc))
    print(plc.id, cs.kind_of(plc), cs.resolve_target(plc, arms))
    # must be (f"{m.id}-C50", "sibling-stem")
PY
```

**Lookback cut:**

```bash
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
/home/miftah/seer/engine/.venv/bin/python -c "
import seer_engine.lab.methods.m0221_cap_weighted_top_n as a
from seer_engine.lab import control_draw as cd
p = a.CapTopParams(50, pick='random', seed=1, trend=None)
print(a.MATCHED.lookback(p));  assert a.MATCHED.lookback(p) == cd.lookback_for(a.DV_N) <= 473
# and the two arms declare, or D17 will never retire the arms they replace
import seer_engine.lab.methods.m0225_cap_weighted_top_n_repaired as b
for m, old in ((a.METHOD, 'M0221-R50'), (b.METHOD, 'M0225-R50')):
    c = [x for x in m.all_candidates() if x.id.endswith('-C50-PLC')][0]
    assert c.supersedes == (old,), (c.id, c.supersedes)
    print(c.id, 'supersedes', c.supersedes)"
```

**Tests:**

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/pytest engine/tests -n auto
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/pytest engine/tests/test_lab_methods.py -n0
/home/miftah/seer/engine/.venv/bin/ruff check engine
```

`PYTHONPATH` is not optional: without it pytest silently tests the main checkout, not this branch.
`test_lab_methods.py` matters most here — it carries
`test_every_recorded_configuration_still_digests_to_its_recorded_digest` (invariant 1) and
`test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`. The second tolerates the window
between the pre-registering commit and the run precisely because `runner.pending_amendment`
resolves: for M0221, 0 recorded against 1 declared; for M0225, 1 recorded (E100) against 2
declared, with the recorded row still matching `E100_AMENDMENT` field for field. If that test
fails on M0225 after Step 4, the cause is an edit to `E100_AMENDMENT` — revert it.

If Postgres is running, `export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres`
first; the DB tests are unrelated to this phase but CI fails if they skip.

**Manual check:** read `$OUT/control_both.txt` with your own eyes. The line for each new arm must
name `sibling-stem` as its rung (not `first-declared`) and `ok` as its verdict. A `first-declared`
rung on either arm means the stem did not resolve and the margin is being quoted against the wrong
book — stop and say so.

**Exit criteria:**

1. `lab control M0221 M0225` reports `M0221-C50-PLC` → `M0221-C50` and `M0225-C50-PLC` →
   `M0225-C50`, both at rung `sibling-stem`, both `ok`, i.e. both inside 0.80x–1.25x on trades
   **and** turnover.
2. Both margins re-stated in `trial_funding.mwr` against SPY TR 7.19%/yr, written into
   `.workflows/plan/honest-control-redraw/phase-3-results.md` and committed.
3. `method_amendments` holds `M0221` seq 1 and `M0225` seq 2; `E100` is still seq 1 with its
   recorded text unchanged.
4. `SELECT count(*) FROM trials WHERE window='test'` is unchanged; no test-window look spent.
5. `pytest engine/tests` and `ruff check engine` green in the worktree.
6. `git hash-object lab/lab.sqlite` recorded before and after each `lab` command.

**Or the stop condition is met** — either new arm lands outside `WARN_BAND` on either axis — in
which case criteria 1 and 2 are replaced by: the measured ratios and the axis that missed are
written into `phase-3-results.md`, nothing is re-drawn, nothing is tuned, and the coordinator is
told that the matched-draw rule does not settle the cap-weighted chassis.

---

## Handoffs

- **Phase 2 (D17 supersession) is what actually unblocks these two, and this phase's half of it
  is the declaration.** `mis_shaped_controls` returns *every* recorded arm outside the band, and
  `M0221-R50` and `M0225-R50` keep their recorded trials forever. The two new arms each carry
  `supersedes=("M0221-R50",)` / `("M0225-R50",)`, which is what Phase 2's rule reads; without it
  an honest, band-clean control retires nothing and both methods stay blocked. Nothing in this
  phase may touch `control_shape.py` or `hardgate.py`, and this phase must not be read as having
  satisfied R4.
- **If the turnover axis misses high, the remedy is NOT applied — here or anywhere.** Settled for
  the whole set (index invariant 12, and the Decisions table): every phase matches **names and
  churn only**, and a turnover miss is a recorded STOP. The one change that would close it is to
  give the drawn names the real arm's own weight *vector* (the k-th drawn name takes the k-th
  largest weight C50 holds that month); it matches the weight distribution exactly and carries no
  identity, but it is a **second** mechanism that would apply to only three of the nine chassis —
  this one, M0047's and M0201's — and would leave those three running a different rule from the
  other six. R1's deliverable is ONE reusable rule, so a rule that needs a per-chassis patch has
  already failed R1, and the honest answer is the measurement. Write both ratios and the axis
  that missed into `phase-3-results.md`; Phase 8's close-out carries the weight-vector remedy
  forward as a stated option for a later plan set.
- **M0047's `M0047-PLC1-MV10`/`-MV20` mis-resolution to `M0047-EQ` is Phase 4's** (R2), and
  `M0202-PLC1-HALF-FAST`'s is Phase 5's. Both are the same `first-declared` guess this phase
  avoids by naming its arms `<target>-PLC`; the fix is identical and is deliberately not
  generalised here.
- **M0221's other five arms and M0225's other six are untouched.** `C100`, `C20`, `C50-SW`, `E50`
  and `E100` have no control arm of their own and D17 does not ask for one. Giving them matched
  placebos would be scope creep and would cost four more trials for a yardstick method nobody
  intends to promote.
- **One observation Phase 8 must carry into the close-out,** measured here read-only and not
  acted on: `M0221-E50` holds C50's *exact names* and records C50's *exact 360 trades*, yet turns
  over 1.60x as much (0.7126 vs 0.445); on M0225 it is 1.68x (0.7674 vs 0.4568). **Turnover on a
  weight-varying chassis is a property of the weight vector, not of the names** — which means a
  control can clear the trade axis by construction and still miss the band on turnover, and that
  is the single most likely way this plan set fails. It is at risk on exactly three chassis
  (M0221/M0225 cap-weighted, M0047 size-weighted under a ceiling, M0201 size-weighted and
  re-sized monthly) and not on the other six, whose equal slots make the turnover ratio follow
  the trade ratio arithmetically. Phases 4 and 5 name the same risk on their own chassis and
  take the same policy.

---

## Rollback

**Before either run** — the block is pre-registration only until `lab run --amend` executes:

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
git revert --no-edit <the pre-registering commit>
```

or, if it is the tip and unpushed, `git revert` it anyway rather than `reset --hard`: the checkout
is shared with the other phases' sessions and a hard reset would take their work with it.

**After a run, there is no rollback.** `trials`, `trial_funding` and `method_amendments` all carry
append-only triggers on update *and* delete. The `Amendment` block must therefore stay in the
method file forever — removing it makes `runner.pending_amendment` refuse the method outright
("the lab has recorded N amendment(s) but the method file declares fewer") and turns
`test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` red. The correct correction is a
journalled finding in Phase 8's close-out saying the arm ran and what it showed.

**Partial state** — M0221 ran and M0225 did not (the stop condition fired at 5c): that is a
coherent end state, not a broken one. M0221's file keeps its committed, recorded amendment;
M0225's file is left unchanged and uncommitted, so the lab sees it exactly as it is today.

> Adopted from `/home/miftah/seer/.workflows/orchestration/honest-control-redraw/PLAN.md` phase 7. Source: `.workflows/plan/honest-control-redraw/phase-7.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 7: M0215 — the sector-capped placebo pair

**Plan set:** `HONEST_CONTROL_REDRAW_PLAN.md`
**Analysis:** `docs/analyzer/20261019-181712-C4K9_code_analyzer.md`
**Satisfies:** R2 (re-draw the mis-shaped arms as an `Amendment` under the existing id), R3 (re-state
the margins in `trial_funding.mwr`, including the ones that worsen), R4 (the arm's own `supersedes` declaration — without it phase 2's D17 rule fires on nothing and the method stays blocked after the measurement)
**Depends on:** Phase 1 — `engine/src/seer_engine/lab/control_draw.py` must exist and hold the
matched-draw rule before this phase's file will import.
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab/methods`

---

## Goal

`m0215_sector_capped_calm_raisers.py` grows one `Amendment` block (seq 1) carrying two
churn-matched placebos, `M0215-CTRL-PLC` and `M0215-CAP4-PLC`, each shaped to the arm it actually
controls and each resolving to that arm on the `sibling-stem` rung. After one `lab run --amend` on
the dev window, M0215 holds a band-clean control for both of the books whose placebo D17 refuses,
and the method's own success condition — which is a comparison *between two placebos* — is
re-stated on the re-drawn pair rather than on the two sticky draws it was written against.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing. No recorded arm is removed; `M0215-HASH` and `M0215-HASH-CAP4` stay in the
file and keep their trials forever (the lab's tables are append-only).

**Renames:** nothing.

**Creates (all inside `engine/src/seer_engine/lab/methods/m0215_sector_capped_calm_raisers.py`):**

- `m0215._check_matched` — params guard (on `CapParams`; **no new params dataclass** — see below)
- `m0215._rows_on`, `m0215._raise_picks`, `m0215._target_shape`, `m0215._parked` — module helpers
- `m0215.MatchedCapPlaceboAllocator` with **allocator id `"M0215-A1"`** (verified free lab-wide:
  155 allocator ids in `discover()`, none is `M0215-A1`)
- `m0215.MATCHED` — the single shared allocator instance both new candidates use
- `m0215.AMENDED` — `date(2026, 10, 19)`
- `m0215._a1` — candidate factory for the amendment
- `m0215.MATCHED_DRAW_AMENDMENT` — the `Amendment` value
- candidate `M0215-CTRL-PLC` (`CapParams(C63, None, "hash", 1)`, declaring
  `supersedes=("M0215-HASH",)`) and candidate `M0215-CAP4-PLC`
  (`CapParams(C63, 4, "hash", 1)`, declaring `supersedes=("M0215-HASH-CAP4",)`)
- `.workflows/plan/honest-control-redraw/phase-7-results.md` — the numbers Phase 8 collects

**Creates NO new params dataclass and no `MATCHED_WARMUP`.** Reconciled 2026-10-19 across the
set: the two new arms reuse, byte for byte, the params **values** of the two arms they replace —
`CapParams(C63, None, "hash", 1)` is `M0215-HASH`'s own value and `CapParams(C63, 4, "hash", 1)`
is `M0215-HASH-CAP4`'s — and the new allocator id `M0215-A1` is the whole of the difference.
`CapParams` already carries `calm`, `cap`, `order` and `seed` (`m0215:69-76`), which is every
input the matched allocator reads, so a `MatchedParams` wrapper would have held nothing new; and
`order="hash"` is the honest value, because the config text is the public record of what an arm
did and a hash-filled book must not describe itself as a raise-ordered one. The
previous-decision slack belongs to `control_draw.lookback_for`
(`PREVIOUS_DECISION_BARS = 26`), not to a `31` guessed here.
- `METHOD.amendments = (MATCHED_DRAW_AMENDMENT,)`
- two rows in the lab database: `method_amendments` (M0215, seq 1) and two `trials` +
  `trial_funding` rows, window `dev`

**Signature changes:** none. `CapParams`, `draw`, `calm_raisers`, `_fill`, `choose`,
`SectorCappedRaiseAllocator`, `_band`, `CAPPED`, `_v`, `C63` and every one of the six original
candidates are left **byte-identical**. `_parked` is a deliberate *copy* of `choose`'s tail, not a
refactor of it, for exactly this reason.

**Requires (from earlier phases):** `engine/src/seer_engine/lab/control_draw.py` (Phase 1). This
phase imports exactly three names from it. See **Assumed contract** below — if Phase 1 spelled them
differently, the reconciler changes one import line and three call sites and nothing else.

**Leaves alone (owned by others):**

- `lab/control_draw.py` — Phase 1 owns it; this phase **consumes it unchanged** and adds nothing
  to it. If the rule needs a new entry point, that is a Phase 1 edit, not this one.
- `lab/control_shape.py`, `lab/hardgate.py`, `commands/lab.py` and their tests — Phase 2.
- `m0227`, `m0243` (Phase 1); `m0221`, `m0225` (Phase 3); `m0047` (Phase 4); `m0201`, `m0202`
  (Phase 5); `m0208` (Phase 6).
- `lab stage`, `web/data/lab.json`, `lab/lab.sqlite` **as a git object** — Phase 8. This phase
  writes rows into the database through `lab run` and leaves the file dirty in the main checkout
  for Phase 8 to stage. It never `git add`s it, never `git checkout`s it, never restores it.
- `lab test`, `SEER_RESEARCH_TEST_STORE` — never touched. The test-window look count stays 4.

### The contract from Phase 1's `control_draw.py`, as Phase 1 actually wrote it

Reconciled 2026-10-19 against `phase-1.md`. Three names are consumed, and these are the real
signatures:

```python
# engine/src/seer_engine/lab/control_draw.py  — PHASE 1 OWNS THIS FILE

def churn(now: Sequence[str], prev: Sequence[str]) -> int:
    """How many names the controlled arm ENTERED this session: ``len(set(now) - set(prev))``."""


def previous_decision_date(data_date: date, cadence: str = "monthly") -> date:
    """The ``data_date`` of the decision before the one being made at ``data_date``.

    Off the published NYSE calendar: takes no History, never returns None, and under a monthly
    cadence answers the last session strictly before the first calendar day of ``data_date``'s
    own month. Checked against ``sim.rules.is_rank_session`` on every monthly decision of the dev
    window, 1996-2015. Look-ahead-free by construction.
    """


def matched_partition(*, pool: Sequence[str], held: AbstractSet[str], keep_n: int, tag: str,
                      seed: int, data_date: date) -> tuple[list[str], list[str]]:
    """``(keep, tail)``: the names the control keeps, then every other name in take order.

    ``held & set(pool)`` sorted by a DATE-FREE hash of (tag, seed, symbol), first ``keep_n`` of
    them; then every remaining pool name — the ones the control does NOT hold first, in a
    MONTH-KEYED hash order of (tag, seed, symbol, YYYY-MM), and the holdings it is dropping
    LAST. ``keep + tail`` is a permutation of ``set(pool)`` — the caller applies its own slot
    count and its own cap. A held name not in today's ``pool`` is absent from both, so the
    caller never has to price a symbol it has no row for.
    """
```

**Four differences from this plan's first draft, all applied below.** The calendar helper is
`previous_decision_date(data_date)`, not `previous_rank_session(market, data_date)` — it takes no
`History` and never returns `None`, so the `prev_date is not None` guard in `_target_shape` goes
and `prepared.history.get(b.market)` is no longer passed. The order helper is
`matched_partition`, not `matched_order`, and it returns `(keep, tail)` rather than one flat
list, so `_run` concatenates before handing the result to `_fill`. It takes a `tag` — the book's
method id, `"M0215"`. And `MATCHED_WARMUP = 31` is replaced by `control_draw.lookback_for`, whose
`PREVIOUS_DECISION_BARS` is 26, measured by Phase 1 over the whole dev calendar.

**The `tail` ordering matters here as much as anywhere**, because `_fill` truncates to the
book's slot count: a dropped holding sorted ahead of a fresh name would be taken straight back
and the realised entry count would fall below the real book's. Phase 1 guarantees
fresh-before-dropped and pins it with a test; this phase relies on the guarantee and does not
re-implement it.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0215_sector_capped_calm_raisers.py` | modify | docstring paragraph after `:34`; imports at `:52` and `:61`; new params + helpers + allocator inserted after `CAPPED = SectorCappedRaiseAllocator()` at `:237`; `_a1` and the `Amendment` block after `_v` at `:243`; `amendments=` added to `METHOD` after `seen_keys` at `:312` |
| `.workflows/plan/honest-control-redraw/phase-7-results.md` | create | the block in **What to record for Phase 8**, filled in |
| `lab/lab.sqlite` (main checkout, **not** this worktree) | append rows | `lab run M0215 --amend` writes one `method_amendments` row and two `trials` + `trial_funding` rows. Left dirty for Phase 8. |

Nothing else. No test file is added: the two new arms are covered by
`test_lab_methods.py::test_allocator_contract` and `::test_candidate_smoke` the moment they are
declared, and the rule's own session-by-session churn test belongs to Phase 1
(`engine/tests/test_lab_control_draw.py`).

---

## What is already true, and why it narrows the job

Read before writing code, because it decides how much the rule has to fix.

`choose` at `m0215:167` already derives the placebo's slot count from the real book:

```python
k = min(len(raisers), top)
```

`raisers` is the uncapped calm-raiser list the *raise* book would fill from, so **the size axis was
never the problem**. The measured turnover ratio (0.43x) is low only because the *names* barely
move. What is wrong is the stickiness, and it is wrong twice over:

- `draw` at `m0215:115-118` keys the hash on the calendar **quarter**, not the month:
  `f"{seed}|{symbol}|{data_date.year:04d}-Q{(data_date.month - 1) // 3 + 1}"` — so the order is
  identical for three consecutive decision sessions;
- `m0215:169` sorts held names **first**:
  `sorted(pool, key=lambda s: (0 if s in held else 1, draw(p.seed, s, data_date), s))` — so even
  across a quarter boundary a name already in the book is re-picked ahead of the whole pool.

Measured consequence: 179 trades against `M0215-CTRL`'s 528 (0.34x) and `M0215-CAP4`'s 500, and
2.045 turnover against 4.780 (0.43x). Both outside `REFUSE_BAND = (0.5, 2.0)`.

So this phase changes exactly one thing about the placebo: where its churn comes from. Everything
else — the SPY-200 switch, the SPY parking, the 1/20 equal slots, the screened member pool, the
FF12 cap, seed 1 — is carried over verbatim.

### Target resolution: the two true targets

Both existing placebos resolve to `M0215-CTRL`, and both resolutions are guesses the ladder
reports as such:

- `M0215-HASH` → `M0215-CTRL` on `first-declared` (its stem `M0215` is not an arm).
- `M0215-HASH-CAP4` → `M0215-CTRL` on `first-declared`, because its stem `M0215-HASH` *is* an arm
  but is itself a placebo and so is dropped by `_eligible_targets` (`control_shape.py:341-356`).
  Its stated job (`m0215:304`) is *"to price what a cap does to any book this shape"*, so its true
  target is `M0215-CAP4`.

Naming the two new arms after their true targets puts both on the strongest rung. **Verified by
running `control_shape.resolve_target` against the amended arm list** (worktree, 2026-10-19):

```
M0215-CTRL-PLC   kind=placebo  target=('M0215-CTRL', 'sibling-stem')
M0215-CAP4-PLC   kind=placebo  target=('M0215-CAP4', 'sibling-stem')
```

and the six originals are unaffected (`M0215-HASH` and `-HASH-CAP4` still read
`('M0215-CTRL', 'first-declared')`; the four signal arms read `kind=''` and are never
shape-checked at all).

### The success condition is a difference between two placebos

`m0215:274-276` reads:

> "Success: a capped variant beats CTRL funded with the worst fall at or under 20%, a positive or
> less negative 2009-2015 edge and a majority of folds, **and its gain over CTRL is larger than
> HASH-CAP4's over HASH** (so the cap helps the raise book specifically)."

That last clause is a difference-in-differences across the placebo pair. Today, in
`trial_funding.mwr` (SPY TR 7.19%/yr on the same deposits):

| half | arms | value |
|---|---|---|
| real | `M0215-CAP4` 10.34 − `M0215-CTRL` 10.62 | **−0.28 pts** |
| placebo | `M0215-HASH-CAP4` 8.62 − `M0215-HASH` 8.66 | **−0.04 pts** |
| condition | −0.28 > −0.04 | **FALSE**, by 0.24 pts |

Repairing the pair therefore re-states the method's own verdict, not merely a margin. The real half
does not move (`CAP4 − CTRL` stays −0.28; those are signal arms and this phase does not touch
them). The placebo half is replaced by `CAP4-PLC − CTRL-PLC`, and the re-stated condition is

    -0.28  >  (M0215-CAP4-PLC.mwr - M0215-CTRL-PLC.mwr)

which this phase pre-registers as still FALSE, by roughly the same margin, because a cap of 4 over
twenty slots drawn blind from the whole screened pool should bind in far fewer months than it does
on a book that is 25% banks and 19% retailers.

---

## Implementation Steps

### Step 1: imports and one docstring paragraph

**File:** `engine/src/seer_engine/lab/methods/m0215_sector_capped_calm_raisers.py:34` (docstring
close) and `:52` (the `Method` import)

**Change:** add a paragraph to the module docstring naming the amendment and why it exists; import
`Amendment` beside `Method`; import `control_draw`.

**Code — insert immediately before the closing `"""` on line 34 (i.e. after the "Rules are
``monthly-hold-frac-gotrade``..." line, with one blank line between):**

```
Amendment 1 (2026-10-19). The two placebos above are mis-shaped and D17 refuses them: the hash is
re-keyed on the calendar quarter and held names sort first, a double stickiness, so each traded 179
times in twenty years against the 528 of ``CTRL`` and the 500 of ``CAP4`` -- 0.34x trades, 0.43x
turnover. Their slot count was already the raise book's own, so the size axis was matched and only
the churn was not. ``CTRL-PLC`` and ``CAP4-PLC`` keep every other part of the frame and take their
entry count each month from the arm each one controls (``lab.control_draw``, the lab's one
matched-draw rule). They also fix a resolution: ``HASH-CAP4`` resolves to ``CTRL`` because its own
stem is a placebo, while the book it exists to price is ``CAP4``; ``<target>-PLC`` names put both
new arms on the ``sibling-stem`` rung. The six recorded configurations are untouched -- the matched
draw rides in its own params dataclass behind its own allocator id, ``M0215-A1``.
```

**Code — replace line 52:**

```python
from seer_engine.lab.method import Amendment, Method
```

**Code — insert one new line immediately *before* line 52**, so the group stays in isort order
(`seer_engine.lab` sorts before `seer_engine.lab.method`):

```python
from seer_engine.lab import control_draw
```

After both edits, the import block at lines 49-62 reads, in full:

```python
from seer_engine import sectors
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab import control_draw
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaisePrepared, _first_bar, live_event
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import events
from seer_engine.lab.methods.m0088_calm_big_raisers import CalmParams, admits, swing
from seer_engine.lab.methods.m0168_banded_calm_raisers import C63, BandedCalmRaiseAllocator, BandParams
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorRow, factor_rows, trend_on
```

**Impact:** nothing executable changes. `hashlib`, `Mapping`, `AbstractSet`, `Decimal`, `Any`,
`np`, `Target`, `equal_weight`, `last_close`, `target_from_close`, `History`, `FactorRow`,
`factor_rows`, `trend_on`, `EXCLUDED`, `RaisePrepared`, `EMPTY_DIVIDENDS` are all already imported
and all are used by the new code.

---

### Step 2: the matched-draw params, helpers and allocator

**File:** `engine/src/seer_engine/lab/methods/m0215_sector_capped_calm_raisers.py:237` — insert
after `CAPPED = SectorCappedRaiseAllocator()` and before `def _v(` at `:240`.

**Change:** add the new params dataclass, four module helpers and the new allocator. Nothing above
line 237 is edited except the imports and the docstring.

**Code — complete, inserted verbatim:**

```python
# --------------------------------------------------------------------------- amendment 1
#
# The churn-matched placebo (2026-10-19). See the module docstring's last paragraph and
# ``seer_engine.lab.control_draw`` for the rule itself; what lives here is this method's half of
# it: which arm is being controlled, and how its shape is read off.


def _check_matched(params: object) -> CapParams:
    """``CapParams``, plus the one thing a control's params may not say.

    The matched draw differs from ``HASH`` / ``HASH-CAP4`` in its allocator id and in nothing
    else, so the params must still read ``order="hash"``. Saying ``"raise"`` would record a
    configuration whose text claims the raise ordering this allocator never performs -- it
    *replays* that ordering to count the real book's entries, and then draws blind.

    Reused and not replaced: ``CapParams`` already carries ``calm``, ``cap``, ``order`` and
    ``seed``, which is every input this allocator reads, so a wrapper dataclass would hold
    nothing new. ``backtest.registry._canon`` renders a dataclass by ``dataclasses.fields()``,
    not by ``as_dict()``, so a new field on ``CapParams`` -- even defaulted, even local to this
    file -- would move the ``config_digest`` of all six recorded M0215 trials, and a
    ``compare=False`` field would make the new arm's configuration identical to the old one's,
    which ``Method.__post_init__`` refuses. Reusing the old value under a new allocator id does
    neither.
    """
    if not isinstance(params, CapParams):
        raise TypeError(f"params must be CapParams, got {type(params).__name__}")
    if params.order != "hash":
        raise ValueError(
            f"the matched draw is a control: order must be 'hash', got {params.order!r}"
        )
    return params


def _rows_on(prepared: Any, members: AbstractSet[str], data_date: date,
             inner: Any) -> list[FactorRow]:
    """``_run``'s factor-row read, lifted so a previous session can use it too."""
    if prepared.factor is None:
        return factor_rows(prepared.history, members, data_date, inner)
    return prepared.factor.rows_on(members, data_date, inner)


def _raise_picks(prepared: Any, rows: list[FactorRow], data_date: date, held: frozenset[str],
                 book: CapParams) -> list[str]:
    """What the controlled arm holds on ``data_date``: ``choose``'s raise path, names only."""
    b = book.calm.ann.base
    raisers = calm_raisers(prepared.history, rows, prepared.calendar, data_date, held, book.calm)
    return _fill([r.symbol for r in raisers], data_date, b.inner.top, book.cap)


def _target_shape(prepared: Any, members: AbstractSet[str], rows: list[FactorRow],
                  data_date: date, book: CapParams) -> tuple[list[str], list[str]]:
    """(the controlled arm's book now, its book at the previous monthly decision session).

    One allocator cannot see another candidate's ``held`` set, so the previous session is replayed
    from an empty book and its result is fed forward as ``held`` for the current one. That is a
    one-step replay and not a guess: all ``held`` buys inside ``calm_raisers`` and ``_fill`` is the
    ordering rule "a name already in the book sorts first", and one month of it is exactly what
    separates an entry from a hold. It reads no bar dated after ``data_date``.
    """
    b = book.calm.ann.base
    prev_date = control_draw.previous_decision_date(data_date)
    prev: list[str] = []
    if trend_on(prepared.history, prev_date, b.inner):
        prev = _raise_picks(prepared, _rows_on(prepared, members, prev_date, b.inner), prev_date,
                            frozenset(), book)
    now = _raise_picks(prepared, rows, data_date, frozenset(prev), book)
    return now, prev


def _parked(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
            picks: list[str], book: CapParams) -> tuple[Target, ...]:
    """``choose``'s tail for an already-chosen list: ``1/top`` each, the rest parked in SPY.

    A copy of ``choose``'s last twelve lines and deliberately not a refactor of them: ``choose`` is
    the recorded path of six closed trials and this file does not touch it. An empty ``picks``
    parks the whole book in SPY, which is what the controlled arm does on a month with no raiser.
    """
    b = book.calm.ann.base
    top = b.inner.top
    close = {r.symbol: r.close for r in rows}
    w = equal_weight(top)
    out: list[Target] = []
    for s in picks:
        t = target_from_close(s, close[s], w)
        if t is not None:
            out.append(t)
    if b.park:
        rest = Decimal(1) - w * len(out)
        mh = history.get(b.market)
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(b.market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
    return tuple(out)


class MatchedCapPlaceboAllocator(SectorCappedRaiseAllocator):
    """M0215's frame filled by a churn-matched blind draw (amendment 1, 2026-10-19).

    The original placebo (``order="hash"``) re-keys its hash on the calendar *quarter* and sorts
    held names first, so its book changes about once a quarter: 179 trades against the 528 of the
    arm it controls, 0.34x, which D17 refuses. Its slot count was already the real book's own
    (``choose`` takes ``k = min(len(raisers), top)``), so the size axis was never the problem --
    only the stickiness was. This allocator keeps everything else and replaces that stickiness with
    the controlled arm's own: each decision session it replays that arm at this date and at the
    previous one, counts the names it *entered*, keeps all but that many of its own holdings in a
    date-free hash order, and draws the rest from the screened members in a month-keyed hash order,
    through the same ``_fill`` (and so the same FF12 cap). Entries match by construction; exits
    follow, because the book's size is the real arm's size that day and the placebo's previous size
    was the real arm's previous size.

    Everything else is ``SectorCappedRaiseAllocator``'s and so M0168's: the same ``prepare``, the
    same ``prepare_market``, the same ``market_fields = ("dividends",)``, the same SPY-200 switch,
    the same SPY parking, the same ``1/20`` slots, the same screened member pool, the same seed.

    A new id, ``M0215-A1``: a trial's configuration is its rules, its allocator id and its params,
    and the six recorded M0215 configurations keep the digests they were recorded under.
    """

    id = "M0215-A1"

    def lookback(self, params: Any) -> int:
        return control_draw.lookback_for(CAPPED.lookback(_check_matched(params)))

    def symbols(self, params: Any) -> tuple[str, ...]:
        return CAPPED.symbols(_check_matched(params))

    def holds(self, params: Any) -> tuple[str, ...]:
        return CAPPED.holds(_check_matched(params))

    def uses_members(self, params: Any) -> bool:
        return CAPPED.uses_members(_check_matched(params))

    def _run(self, prepared: Any, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: Any) -> tuple[Target, ...]:
        book = _check_matched(p)
        b = book.calm.ann.base
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        if not trend_on(prepared.history, data_date, b.inner):
            return ()
        rows = _rows_on(prepared, members, data_date, b.inner)
        now, prev = _target_shape(prepared, members, rows, data_date, book)
        n = len(now)
        pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != b.market)
        keep, tail = control_draw.matched_partition(
            pool=pool, held=held, keep_n=max(0, n - control_draw.churn(now, prev)),
            tag="M0215", seed=book.seed, data_date=data_date,
        )
        # keep + tail is the whole pool in take order, fresh names ahead of dropped holdings;
        # `_fill` truncates it to n under the FF12 cap, exactly as it truncates the raise order.
        return _parked(prepared.history, rows, data_date,
                       _fill(keep + tail, data_date, n, book.cap), book)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(RaisePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check_matched(params))


    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RaisePrepared):
            raise TypeError(f"prepared must be RaisePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check_matched(params))


MATCHED = MatchedCapPlaceboAllocator()
```

**Impact:**

- `targets` and `targets_prepared` **must** be overridden anyway, to route through this class's
  own `_run`. They no longer have to be overridden for a *type* reason: the params are a plain
  `CapParams`, so the inherited `_check(params)` would accept them — which is precisely why
  `_check_matched`'s `order == "hash"` assertion earns its place, since nothing else now stops a
  raise-ordered value reaching this allocator.
- `MATCHED` is a single module-level instance shared by both candidates, because
  `test_allocator_ids_are_unique_across_methods` (`test_lab_methods.py:108-115`) asserts
  `seen is c.allocator` for every candidate sharing an allocator id.
- The allocator stays market-aware (it inherits `market_fields` and `prepare_market`), so
  `test_allocator_contract` requires it to target nothing on the history-only path. The
  `len(prepared.calendar) == 0` guard is the first statement of `_run`, so it does.
- Lookback is `control_draw.lookback_for(253)` = `253 + 26` = **279**, under the 473-bar smoke
  fixture (plan invariant 11). Verified: `CAPPED.lookback(CapParams(C63, None, "hash", 1))` is
  253, and `PREVIOUS_DECISION_BARS` is 26 — measured by Phase 1 over every monthly decision of
  the dev window rather than estimated per file.
- Cost: two extra `calm_raisers` evaluations and one extra `_rows_on` per decision session, so the
  arm runs roughly three times slower than a signal arm. 240 decision sessions over the dev window;
  it is minutes, not hours.
- No existing symbol is touched, so no recorded `config_digest` can move.

---

### Step 3: the candidate factory for the amendment

**File:** `engine/src/seer_engine/lab/methods/m0215_sector_capped_calm_raisers.py:243` — insert
after the existing `_v` helper (which ends at line 243) and before `METHOD = Method(` at `:246`.

**Change:** add the amendment's own `added` date and candidate factory. `_v` is left untouched so
the six originals keep `added=ADDED` (2026-10-17).

**Code:**

```python
AMENDED = date(2026, 10, 19)


def _a1(suffix: str, params: CapParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate, with the declaration of which recorded arm it replaces.

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``): declared, never
    inferred. It is what pairs each new arm with the right old one here -- ``HASH`` and
    ``HASH-CAP4`` BOTH resolve to ``M0215-CTRL``, so a rule that matched targets would have let
    ``CTRL-PLC`` excuse the capped arm as well, which was never scored against ``CTRL`` in
    spirit."""
    return Candidate(id=f"M0215-{suffix}", family="M0215", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=AMENDED,
                     owner_inputs=(), supersedes=supersedes)
```

**Impact:** `owner_inputs=()` is correct and must stay empty — `candidate_owner_inputs` derives it
from `rules` plus `holds()`, `holds()` returns `("SPY",)` exactly as `CAPPED`'s does, and `SPY` is
in `sim.rules.DEFAULT_ETFS`. This matches the six originals.

---

### Step 4: the `Amendment` block

**File:** `engine/src/seer_engine/lab/methods/m0215_sector_capped_calm_raisers.py` — insert after
Step 3's `_a1`, still before `METHOD = Method(`.

**Change:** the pre-registration. Every word of `why`, `hypothesis` and `expected_failure` is
written and committed **before** `lab run --amend` is invoked (plan invariant 2). Nothing here is
edited after a result is seen.

**Code — complete:**

```python
MATCHED_DRAW_AMENDMENT = Amendment(
    added=AMENDED,
    why=(
        "Both hash-order placebos trade a third as often as the books they control (179 against "
        "528 and 500: 0.34x trades, 0.43x turnover), so neither quoted lead is evidence -- "
        "re-draw each to the shape of the arm it actually controls"
    ),
    hypothesis=(
        "Written and committed before the run. M0215's two placebos re-key their hash on the "
        "calendar quarter (`draw`) and sort held names first (`choose`), a double stickiness, so "
        "each turned over 179 times in twenty years against M0215-CTRL's 528 and M0215-CAP4's "
        "500 -- 0.34x trades and 0.43x turnover, outside the [0.50, 2.00] band D17 refuses on. "
        "Their slot count was already the raise book's own (k = min(len(raisers), top)), so the "
        "size axis was matched and only the churn was not; that is all this amendment changes. "
        "CTRL-PLC and CAP4-PLC keep the whole frame -- the SPY-200 switch, the SPY parking, "
        "twenty 1/20 slots, the screened member pool, the FF12 cap where the controlled arm has "
        "one, seed 1 -- and take their entry count each month from the arm each one controls, "
        "keeping the rest of the book in a date-free hash order. They also repair a resolution: "
        "HASH-CAP4 today resolves to CTRL because its own stem is a placebo, while the book it "
        "exists to price is CAP4; CTRL-PLC and CAP4-PLC resolve to CTRL and CAP4 on the "
        "sibling-stem rung. Three predictions, in trial_funding.mwr against SPY TR 7.19%/yr on "
        "the same deposits. (1) SHAPE: both arms land inside 0.80-1.25 of their own target on "
        "both axes -- CTRL-PLC near 528 trades and 4.78 turnover, CAP4-PLC near 500 and 4.56. "
        "(2) DIRECTION: an honestly-shaped blind book trades about three times as often and pays "
        "about three times the Gotrade fee bill, so both new arms earn LESS than the 8.66% and "
        "8.62% the sticky draws recorded, and both quoted leads WIDEN -- CTRL's +1.96 points over "
        "its placebo and CAP4's +1.72 each grow by between 0.3 and 1.5 points a year. (3) THE "
        "SUCCESS CONDITION: this method's own bar is a difference between two placebos ('its gain "
        "over CTRL is larger than HASH-CAP4's over HASH'), so re-drawing the pair re-states the "
        "verdict and not merely a margin. The real half does not move -- CAP4 minus CTRL is -0.28 "
        "points and stays there. The placebo half, -0.04 today, is predicted to stay within 0.15 "
        "points of zero, because a cap of four over twenty slots drawn blind from the whole "
        "screened pool binds in far fewer months than it does on a book that is 25% banks and 19% "
        "retailers. So the re-stated condition, -0.28 > (CAP4-PLC minus CTRL-PLC), still FAILS by "
        "roughly the 0.2 to 0.3 points it fails by today, and M0215's standing verdict survives "
        "its honest control unchanged."
    ),
    expected_failure=(
        "The honest draws may earn MORE, not less. The quarter-keyed draw froze a 2008-era book it "
        "could not exit and fell 21.9% against CTRL's 18.7%; a book re-drawn every month rides the "
        "recovery and pays its fees out of a bigger number, so both leads could NARROW or reverse. "
        "If they do, the finding is that the +1.96 in this file was an artifact of a handicapped "
        "opponent and that the frame -- twenty equal slots behind the SPY-200 switch with the rest "
        "parked in SPY -- is what the book earns, not the raise signal. That is reported as the "
        "finding and not re-drawn (design section 4). Second, the churn match is estimated rather "
        "than known: one candidate's allocator cannot see another's held set, so the previous "
        "decision session is replayed from an empty book and fed forward one step, and if that "
        "one-step replay mis-states the entry count the ratios miss the 0.80-1.25 match band. The "
        "measured ratios are then recorded and the work stops; the seed and the re-key period are "
        "not dials. Third, a cap of four may bind more often on a blind draw than predicted if the "
        "screened pool is itself concentrated, which would make the placebo half of the "
        "difference-in-differences larger than 0.15 points and could flip the re-stated condition "
        "on what is noise rather than a cap effect -- in which case the honest reading is that "
        "twenty names cannot resolve a 0.3 point cap effect at all. Fourth, the extra replay "
        "roughly triples the allocator's per-session work: the run is slower and nothing else."
    ),
    candidates=(
        _a1("CTRL-PLC", CapParams(C63, None, "hash", 1),
            "Placebo, re-drawn to M0215-CTRL's own shape: as many slots and as many fresh names "
            "each month as the uncapped raise book, filled in hash order by members that know "
            "nothing about dividends",
            supersedes=("M0215-HASH",)),
        _a1("CAP4-PLC", CapParams(C63, 4, "hash", 1),
            "Placebo capped at 4 per industry, re-drawn to M0215-CAP4's own shape and filled in "
            "hash order, to price what a cap does to any book this shape",
            supersedes=("M0215-HASH-CAP4",)),
    ),
)
```

**Impact — the two checks this block has to clear, argued:**

*`config_digest` safety (plan invariant 1).* `config_text` is
`rules=<_canon> / allocator=<id> / params=<_canon>`. `CapParams` gains no field, loses no field and
is not reordered, so every one of the six recorded M0215 digests is byte-identical. The new arms
carry a brand-new dataclass; `_canon`'s dataclass branch emits `type(value).__name__` followed by
its `fields()`, and the new arms reuse `CapParams` values the lab already holds — so their
`params=` line is byte-identical to `M0215-HASH`'s and `M0215-HASH-CAP4`'s, and the
`allocator=<M0215-A1>` line against `<M0215>` is the whole of the difference.
`test_every_recorded_configuration_still_digests_to_its_recorded_digest` stays green.

*`Method.__post_init__` uniqueness.* It shares one `ids` set and one `digests` set across the
originals and every amendment.

- **ids:** `M0215-CTRL-PLC` and `M0215-CAP4-PLC` are not among
  `{CTRL, CAP3, CAP4, CAP5, HASH, HASH-CAP4}`. Both match `backtest.dev._ID` (verified).
- **configurations:** both new arms share `rules=monthly-hold-frac-gotrade` with all six, but their
  `allocator=<M0215-A1>` line differs from the originals' `allocator=<M0215>`, so neither digest
  can collide with an original however their params read. The two new arms differ from each other
  in `book.cap` (`None` vs `4`), so they do not collide with each other.
- **allocator id lab-wide:** `M0215-A1` is free. Measured over `lab.method.discover()`:
  155 distinct allocator ids, `M0215-A1` absent.

*Marker discipline (plan invariant 3).* Checked against the live
`control_shape.DOSE_MARKERS` / `DRAW_MARKERS`:

```
dose markers hit: []
draw markers hit: ['placebo', 'hash order']
```

Both rationales are single-line (`Candidate.__post_init__` refuses `\n`). The new arms therefore
classify as `KIND_PLACEBO` and *are* shape-checked — which is the whole point. Phrasing either of
them as dose-response would make the refusal vanish without fixing anything and is forbidden
outright.

---

### Step 5: wire the amendment into `METHOD`

**File:** `engine/src/seer_engine/lab/methods/m0215_sector_capped_calm_raisers.py:312` — the line
closing `seen_keys=(...)`.

**Change:** add the `amendments` field. Lines 306-313 become, in full:

```python
    seen_keys=(
        "concept:dividend-increase-drift",
        "concept:dividend-change",
        "concept:low-volatility-filter",
        "concept:sector-cap",
        "concept:hash-order-yardstick",
    ),
    amendments=(MATCHED_DRAW_AMENDMENT,),
)
```

**Impact:** `METHOD.all_candidates()` grows from six to eight; `candidates` still returns the
original six. `seen_keys` is left alone — `concept:hash-order-yardstick` already covers the pair and
an amendment does not re-reserve concepts.

---

### Step 6: verify green, then commit — the commit IS the pre-registration

**Change:** run the tree's checks, then commit **only** this method file, by pathspec. This phase
shares one worktree and one index with phases 1-6 (memory: *Seer swarms share one worktree*), so
nothing is staged and nothing is reset.

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw

export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite
export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
export PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PY=/home/miftah/seer/engine/.venv/bin/python
RUFF=/home/miftah/seer/engine/.venv/bin/ruff
OUT=/tmp/claude-1000/-home-miftah-seer/phase7
mkdir -p "$OUT"

# the file imports and the two arms resolve as intended
$PY -c "
import seer_engine.lab.methods.m0215_sector_capped_calm_raisers as m
from seer_engine.lab import control_shape as cs
from seer_engine.lab.method import config_digest
arms = m.METHOD.all_candidates()
print('arms:', len(arms))
for c in arms[-2:]:
    print(c.id, cs.kind_of(c), cs.resolve_target(c, arms), m.MATCHED.lookback(c.params))
print('digests unique:', len({config_digest(c) for c in arms}) == len(arms))
"

$RUFF check engine
$PY -m pytest engine/tests/test_lab_methods.py -q
$PY -m pytest engine/tests -q
```

Expected from the probe: `arms: 8`, both new arms `placebo` on `sibling-stem` to `M0215-CTRL` and
`M0215-CAP4`, lookback `279`, `digests unique: True`, and both `supersedes` tuples as the
index's mapping gives them (`CTRL-PLC` -> `M0215-HASH`, `CAP4-PLC` -> `M0215-HASH-CAP4`).

Then commit by pathspec only:

```bash
git -C /home/miftah/.worktrees/seer/honest-control-redraw commit \
  -m "lab: M0215 amendment 1 pre-registered — the two placebos re-drawn to the shape of the arms they control

The hash-order pair re-keys on the calendar quarter and sorts held names first, so each traded 179
times against CTRL's 528 and CAP4's 500 (0.34x trades, 0.43x turnover) and D17 refuses both. Their
slot count was already the raise book's own, so only the churn was wrong. CTRL-PLC and CAP4-PLC
keep the whole frame and take their entry count each month from the arm each one controls, through
lab/control_draw. They also put both arms on the sibling-stem rung, so HASH-CAP4's quiet
mis-resolution to CTRL is repaired. New allocator id M0215-A1 over the two replaced arms' own
CapParams values, reused byte for byte: no recorded config_digest moves, and the allocator= line
is the whole of the difference. Each new arm declares the arm it supersedes (CTRL-PLC retires
HASH, CAP4-PLC retires HASH-CAP4), which is what pairs them correctly -- both old arms resolve
to M0215-CTRL, so a supersession rule that matched targets would have let one new arm excuse
both.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- engine/src/seer_engine/lab/methods/m0215_sector_capped_calm_raisers.py

git -C /home/miftah/.worktrees/seer/honest-control-redraw status --porcelain \
  -- engine/src/seer_engine/lab/methods/m0215_sector_capped_calm_raisers.py
```

The last command must print **nothing**. `runner.preflight` → `registry_problem` runs
`git status --porcelain -- <basename>` with `cwd=<the file's directory>` and refuses a dirty or
untracked file; it checks this one file only, which is why phases 1-6 may be mid-edit in the same
checkout without blocking this run.

**Impact:** from this commit on, the pre-registration is frozen. If anything below says the
hypothesis was wrong, the hypothesis stays as written and the result is the finding.

---

### Step 7: the dev run

**Change:** one `lab run --amend`. No pipes anywhere — a piped `lab` command hides its exit code
(memory: *A piped lab command hides its exit code*), so output is redirected to a file and `$?` is
read on the next line.

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw

# the lab database's identity before (a read-only query never migrates; a lab command does)
git -C /home/miftah/seer hash-object lab/lab.sqlite
# expected at the time of writing: 3969f1fa5d2066a42ed47716dd05a66050073592

SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine -v lab run M0215 --amend \
  > /tmp/claude-1000/-home-miftah-seer/phase7/m0215-amend.log 2>&1
echo "lab run --amend exit: $?"

cat /tmp/claude-1000/-home-miftah-seer/phase7/m0215-amend.log

git -C /home/miftah/seer hash-object lab/lab.sqlite
```

Exit codes: `0` ok, `2` the lab's rules refused the request, `1` an error. On `2`, read the message
— the usual causes are a dirty method file (Step 6's `status` was not empty) or a configuration
that already ran — fix the cause, do not re-run blind.

**The hash will move, and it must not be restored.** This is a real write: one `method_amendments`
row and two `trials` + `trial_funding` rows. Record both hashes in the phase's notes for Phase 8.
Never `git checkout`, `git restore` or `git stash` `lab/lab.sqlite` in this phase — other phases
are writing to the same file concurrently and the run's rows must survive. `lab stage` is **not**
run here (plan invariant 8).

**Impact:** M0215's status does not move (an amendment appends trials, it never moves a status).
The luck gate's N does not move: no method id is spent. The test-window look count stays 4.

---

### Step 8: measure the shape and the two margins

**Change:** read nothing but results. `lab control` is a `lab` command and migrates on connect, so
hash before and after it too; the funding read is a read-only `sqlite3` URI and does not.

```bash
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab control M0215 \
  > /tmp/claude-1000/-home-miftah-seer/phase7/m0215-control.log 2>&1
echo "lab control exit: $?"
cat /tmp/claude-1000/-home-miftah-seer/phase7/m0215-control.log

sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" "
SELECT t.candidate_id, t.n, t.trades, round(t.turnover,3), round(t.max_drawdown,3),
       round(100*f.mwr,2) AS mwr_pct, round(100*f.spy_tr_mwr,2) AS spy_pct
FROM trials t JOIN trial_funding f ON f.trial_n = t.n
WHERE t.method_id = 'M0215' AND t.window = 'dev'
ORDER BY t.n;"

sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" "
SELECT method_id, seq, added, substr(source_sha,1,12), run_at
FROM method_amendments WHERE method_id = 'M0215';"
```

**The bands to read the shape against** (`WARN_BAND` is 0.80–1.25 and is the bar; `REFUSE_BAND`
0.50–2.00 is not good enough):

| new arm | target | target trades | trades must land in | target turnover | turnover must land in |
|---|---|---|---|---|---|
| `M0215-CTRL-PLC` | `M0215-CTRL` (trial 707) | 528 | **422 – 660** | 4.780 | **3.824 – 5.975** |
| `M0215-CAP4-PLC` | `M0215-CAP4` (trial 709) | 500 | **400 – 625** | 4.562 | **3.650 – 5.703** |

**Impact:** nothing is written. The numbers below go into the phase note Phase 8 reads.

---

## Verification

**Build:** `/home/miftah/seer/engine/.venv/bin/ruff check engine` (from the worktree root; CI lint
is E9 and F minus F401).

**Tests:**

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
PYTHONPATH=$PWD/engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -q
```

`PYTHONPATH` is not optional: without it pytest silently tests the main checkout instead of the
branch (memory: *Worktree tests need PYTHONPATH*). The three tests that matter here, all inside
`engine/tests/test_lab_methods.py`:

- `test_every_recorded_configuration_still_digests_to_its_recorded_digest` — the invariant-1 proof.
  Must be green both before and after the run.
- `test_every_method_file_hashes_to_its_recorded_sha` — goes green through
  `runner.pending_amendment` while the block is committed-but-unrun, and through
  `store.latest_source_sha` once the run has recorded it.
- `test_allocator_contract[M0215-CTRL-PLC]` / `[M0215-CAP4-PLC]` — P4 identity and no-lookahead on
  the 473-bar smoke fixture. Both are market-aware, so the kit asserts they target **nothing** on
  the history-only path; the `len(prepared.calendar) == 0` guard is `_run`'s first statement.
- `test_allocator_ids_are_unique_across_methods` — `M0215-A1` must be one object.

**Manual check:**

1. `lab control M0215` prints `M0215-CTRL-PLC` controlling `M0215-CTRL` and `M0215-CAP4-PLC`
   controlling `M0215-CAP4`, both on the `sibling-stem` rung, both `ok`. The two old arms still
   appear and still refuse — retiring them is Phase 2's supersession rule, not this phase's job.
2. The `method_amendments` query returns exactly one row for M0215: `seq 1`.
3. `git -C /home/miftah/seer hash-object lab/lab.sqlite` moved across the run and was **not**
   restored.
4. `web/data/lab.json` is untouched and the lab-snapshot test is expected red mid-batch. Do not try
   to make it green (plan invariant 8).

**Exit criteria:**

- Both new arms inside `WARN_BAND` (0.80–1.25) on **both** trades and turnover against their own
  targets, at the bounds tabulated in Step 8.
- Both margins re-stated in `trial_funding.mwr` against SPY TR 7.19%/yr:
  `M0215-CTRL` − `M0215-CTRL-PLC` beside today's `10.62 − 8.66 = +1.96`, and
  `M0215-CAP4` − `M0215-CAP4-PLC` beside today's `10.34 − 8.62 = +1.72`.
- The difference-in-differences re-stated and judged: `−0.28 > (CAP4-PLC − CTRL-PLC)` — true or
  false, by how much, and whether that agrees with the pre-registered prediction that it stays
  false.
- `pytest engine/tests` and `ruff check engine` green.

### Stop condition

If either new arm lands **outside** `WARN_BAND` on either axis: **record the measured ratios and
stop.** Write them into the phase note for Phase 8 and say which axis missed and by how much. Do
not change the seed, do not change the hash's re-key period, do not add a third arm, and do not run
`lab run --amend` a second time for a better shape — plan invariant 4 admits a second amendment on
the same book only for a missed *shape*, and even then the second rule is a Phase 1 change to
`control_draw.py`, never a tuned seed here (design §4).

If the shape lands but a margin **worsens or reverses**, that is not a failure — it is the finding.
Report it as written in `expected_failure` and change nothing.

---

## What to record for Phase 8

**Write it to `.workflows/plan/honest-control-redraw/phase-7-results.md` and commit it by
pathspec.** That path is the set's one results-file convention (`phase-N-results.md`, N in 1..7)
and the only place Phase 8 collects this phase's numbers from. Nothing else in this phase writes
a number anywhere a later reader will look: no `lab note`, no `lab insight`, no edit to the plan
index, no `lab stage`.

One block, to be pasted into that file. Fill the bracketed cells from Step 8's queries.

```
M0215 — the sector-capped placebo pair

shape (WARN_BAND 0.80-1.25, both axes):
  M0215-CTRL-PLC vs M0215-CTRL   trades [ ]/528 = [ ]x   turnover [ ]/4.780 = [ ]x   -> [ok|miss]
  M0215-CAP4-PLC vs M0215-CAP4   trades [ ]/500 = [ ]x   turnover [ ]/4.562 = [ ]x   -> [ok|miss]
  resolution: both sibling-stem (the old pair resolved first-declared, HASH-CAP4 to the wrong arm)

margins, trial_funding.mwr, SPY TR 7.19%/yr:
  old  M0215-CTRL 10.62 - M0215-HASH      8.66 = +1.96 pts   (control 0.34x / 0.43x: not evidence)
  new  M0215-CTRL 10.62 - M0215-CTRL-PLC  [ ]  = [ ] pts
  old  M0215-CAP4 10.34 - M0215-HASH-CAP4 8.62 = +1.72 pts   (control 0.34x / 0.43x: not evidence)
  new  M0215-CAP4 10.34 - M0215-CAP4-PLC  [ ]  = [ ] pts
  pre-registered direction: both WIDEN by 0.3-1.5 pts.  observed: [widened|narrowed|reversed]

the method's own success condition (a difference between two placebos, m0215:274-276):
  real half      CAP4 - CTRL             = -0.28 pts   (unchanged; signal arms were not touched)
  old placebo    HASH-CAP4 - HASH        = -0.04 pts   ->  -0.28 > -0.04  FALSE by 0.24 pts
  new placebo    CAP4-PLC - CTRL-PLC     = [ ] pts     ->  -0.28 > [ ]    [FALSE|TRUE] by [ ] pts
  pre-registered: still FALSE, placebo half within 0.15 pts of zero.  observed: [ ]
  one sentence:  M0215's standing verdict [survived|did not survive] its honest control, because [ ]

declarations (check against the index's supersession mapping):
  M0215-CTRL-PLC supersedes M0215-HASH        M0215-CAP4-PLC supersedes M0215-HASH-CAP4
  Both old arms resolve to M0215-CTRL, so target equality would have let one new arm excuse
  both; the declaration is what pairs them correctly.

bookkeeping:
  lab.sqlite git hash-object before [ ] / after [ ]
  method_amendments: M0215 seq 1, added 2026-10-19, source_sha [ ]
  trials added: 2 (dev).  test-window looks still 4.  lab stage NOT run.
```

---

## Handoffs

- **Phase 1** owns `control_draw.py` entirely. If the matched draw needs a second entry point for
  a capped book, or if `previous_decision_date` needs a cadence other than monthly, that is a
  Phase 1 edit. This phase added nothing to the helper and must not.
- **Phase 2 (R4) owns the only thing that actually unblocks `lab promote` for M0215, and this
  phase's half of it is the two declarations.** The old `M0215-HASH` and `M0215-HASH-CAP4` trials
  are recorded forever and `mis_shaped_controls` returns every recorded arm outside the band, so
  after this phase lands D17 **still refuses M0215** until Phase 2's rule is in. That is expected
  and is not this phase's bug.

  **The pairing question this phase raised in planning is now decided, and deciding it is why
  Phase 2's predicate changed.** Both old arms resolve to `M0215-CTRL` — `HASH-CAP4` because its
  own stem is a placebo and the ladder steps past it — so under the draft's "same `target_id`"
  rule `M0215-CTRL-PLC` would have excused **both**, including the capped arm, which exists to
  price what a cap does and was never scored against `CTRL` in spirit. That is the "too loose"
  half of the argument against target equality, and this method is where it is sharpest. Phase
  2's rule is now an **explicit declaration**: `M0215-CTRL-PLC` carries
  `supersedes=("M0215-HASH",)` and `M0215-CAP4-PLC` carries `supersedes=("M0215-HASH-CAP4",)`,
  so each old arm is retired by the arm drawn to replace it and by no other. Getting those two
  tuples right is this phase's whole contribution to R4; this phase still touches no
  `control_shape.py`.
- **Phase 8** owns the single `lab stage`, the merge and the push. This phase leaves
  `/home/miftah/seer/lab/lab.sqlite` dirty on purpose.
- **Not done here, deliberately:** `M0215-CAP3-PLC` and `M0215-CAP5-PLC`. CAP3 and CAP5 have no
  recorded placebo at all, so D17 has nothing to refuse for them and adding arms for them would be
  new measurement outside R2's scope ("re-draw every mis-shaped control arm"). If the owner later
  wants the whole cap ladder priced against matched blind books, that is a second amendment and a
  separate decision.
- **Not done here:** the stale sentences on `seertrade.site/sera/methods/M0215` quoting the +1.96
  and +1.72 against the sticky draws. Updating a published method page is the
  `update-stale-sera-methods-page` skill's job and belongs to Phase 8's close-out or to a later
  session, not to a method-file phase.
- **Not done here:** the half-matched `k = min(len(raisers), top)` in `choose` at `m0215:167` takes
  its slot count from the *uncapped* raiser list even when `cap` is set, so `M0215-HASH-CAP4`'s
  book could come up shorter than `M0215-CAP4`'s. The new arms avoid it by taking `n = len(now)`
  from the controlled arm's realised picks. `choose` itself is frozen and is not touched.

## Rollback

- **Before Step 7's run:**
  `git -C /home/miftah/.worktrees/seer/honest-control-redraw revert --no-edit <the Step 6 commit>`
  undoes the whole phase. Until `lab run --amend` executes, the `Amendment` block is
  pre-registration and nothing else; no lab row exists.
- **After Step 7's run:** nothing in the lab database is reversible. `trials`, `trial_funding` and
  `method_amendments` all carry append-only triggers on UPDATE and DELETE. The `Amendment` block
  must therefore stay in the file forever — deleting it would make
  `test_every_method_file_hashes_to_its_recorded_sha` and `pending_amendment` disagree with the
  recorded row. The correct rollback is a journalled `lab insight` saying the arms were run and
  what they showed. **This is exactly why Step 6 puts the entire pre-registration in the commit
  that precedes the run.**
- **Never:** `git checkout`/`restore`/`stash` on `/home/miftah/seer/lab/lab.sqlite`, and never
  `git pull --rebase` while the batch is running — a rebase replays a stale `lab.sqlite` over the
  live one that other phases are writing to (memory: *A rebase replays a stale lab.sqlite*).
